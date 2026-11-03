#!/usr/bin/env python3
"""Version project domain intent and render Cloudflare ingress without live writes."""
import argparse
import copy
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit
import uuid

SCHEMA = 'gserver.domains.v1'
SLUG = re.compile(r'[a-z][a-z0-9-]{0,39}\Z')
REVISION = re.compile(r'[a-f0-9]{64}\Z')
LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')


class DomainError(Exception):
    pass


def require(value, code):
    if not value:
        raise DomainError(code)


def keys(value, required, optional=()):
    require(isinstance(value, dict) and set(required) <= value.keys()
            and value.keys() <= set(required) | set(optional), 'INVALID_FIELDS')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hostname(value):
    require(isinstance(value, str) and value and not value.endswith('.'), 'INVALID_HOSTNAME')
    try:
        result = value.encode('idna').decode('ascii').lower()
    except UnicodeError:
        raise DomainError('INVALID_HOSTNAME') from None
    require(len(result) <= 253 and len(result.split('.')) >= 2
            and all(LABEL.fullmatch(part) for part in result.split('.')), 'INVALID_HOSTNAME')
    try:
        ipaddress.ip_address(result)
    except ValueError:
        return result
    raise DomainError('IP_HOSTNAME_FORBIDDEN')


def origin(value):
    require(isinstance(value, str) and not any(x in value for x in ('?', '#', '\\'))
            and not any(ch.isspace() or ord(ch) < 32 for ch in value), 'INVALID_ORIGIN')
    try:
        parsed = urlsplit(value)
        host, port = parsed.hostname, parsed.port
    except ValueError:
        raise DomainError('INVALID_ORIGIN') from None
    require(parsed.scheme in ('http', 'https') and host and port and 1 <= port <= 65535
            and parsed.username is None and parsed.password is None and parsed.path in ('', '/'), 'INVALID_ORIGIN')
    require(host in ('127.0.0.1', '::1', 'localhost') or (LABEL.fullmatch(host) and not host.isdecimal()),
            'NONLOCAL_ORIGIN_FORBIDDEN')
    return f'{parsed.scheme}://[{host}]:{port}' if ':' in host else f'{parsed.scheme}://{host}:{port}'


def validate_policy(policy):
    keys(policy, ('schema', 'projects'))
    require(policy['schema'] == SCHEMA and isinstance(policy['projects'], dict) and policy['projects'], 'POLICY_INVALID')
    policy = copy.deepcopy(policy)
    owners = {}
    for project, config in policy['projects'].items():
        require(isinstance(project, str) and SLUG.fullmatch(project), 'INVALID_PROJECT')
        keys(config, ('repository', 'zones', 'endpoints'))
        require(isinstance(config['repository'], str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', config['repository']), 'INVALID_REPOSITORY')
        require(isinstance(config['zones'], list) and config['zones'], 'ZONES_REQUIRED')
        config['zones'] = sorted(set(hostname(zone) for zone in config['zones']))
        require(isinstance(config['endpoints'], dict) and config['endpoints'], 'ENDPOINTS_REQUIRED')
        for endpoint, contract in config['endpoints'].items():
            require(isinstance(endpoint, str) and SLUG.fullmatch(endpoint), 'INVALID_ENDPOINT')
            keys(contract, ('origin', 'tunnel', 'callbacks'), ('access', 'application_auth'))
            require(('access' in contract) != ('application_auth' in contract), 'AUTH_CONTRACT_REQUIRED')
            contract['origin'] = origin(contract['origin'])
            try:
                contract['tunnel'] = str(uuid.UUID(contract['tunnel']))
            except (ValueError, AttributeError, TypeError):
                raise DomainError('INVALID_TUNNEL_ID') from None
            address = (contract['tunnel'], contract['origin'])
            require(address not in owners or owners[address] == project, 'ORIGIN_OWNERSHIP_CONFLICT')
            owners[address] = project
            require(isinstance(contract['callbacks'], list) and all(
                isinstance(path, str) and re.fullmatch(r'/[A-Za-z0-9/_-]*', path)
                for path in contract['callbacks']), 'INVALID_CALLBACK_PATH')
            if 'access' in contract:
                access = contract['access']
                keys(access, ('team_name', 'aud_tags'))
                require(isinstance(access['team_name'], str) and LABEL.fullmatch(access['team_name']), 'INVALID_ACCESS_TEAM')
                require(isinstance(access['aud_tags'], list) and access['aud_tags'] and all(
                    isinstance(tag, str) and re.fullmatch(r'[A-Za-z0-9_-]{8,128}', tag)
                    for tag in access['aud_tags']), 'INVALID_ACCESS_AUDIENCE')
            else:
                require(isinstance(contract['application_auth'], str) and SLUG.fullmatch(contract['application_auth']), 'INVALID_APP_AUTH_CONTRACT')
    return policy


def compile_bindings(policy, bindings):
    policy = validate_policy(policy)
    require(isinstance(bindings, list), 'INVALID_BINDINGS')
    normalized, tunnels, callbacks, identities, hosts = [], {}, [], set(), set()
    for binding in bindings:
        keys(binding, ('project', 'endpoint', 'hostname'), ('aliases',))
        project, endpoint = binding['project'], binding['endpoint']
        require(isinstance(project, str) and project in policy['projects'], 'PROJECT_NOT_REGISTERED')
        config = policy['projects'][project]
        require(isinstance(endpoint, str) and endpoint in config['endpoints'], 'ENDPOINT_NOT_REGISTERED')
        require((project, endpoint) not in identities, 'DUPLICATE_ENDPOINT')
        identities.add((project, endpoint))
        primary = hostname(binding['hostname'])
        aliases = binding.get('aliases', [])
        require(isinstance(aliases, list) and len(aliases) <= 10, 'INVALID_ALIASES')
        aliases = sorted(set(hostname(alias) for alias in aliases) - {primary})
        contract = config['endpoints'][endpoint]
        for host in [primary] + aliases:
            require(any(host == zone or host.endswith('.' + zone) for zone in config['zones']), 'ZONE_NOT_ALLOWED')
            require(host not in hosts, 'HOSTNAME_CONFLICT')
            hosts.add(host)
            rule = {'hostname': host, 'service': contract['origin']}
            if 'access' in contract:
                access = contract['access']
                rule['originRequest'] = {'access': {'required': True, 'teamName': access['team_name'], 'audTag': access['aud_tags']}}
            tunnels.setdefault(contract['tunnel'], []).append(rule)
        normalized.append({'project': project, 'endpoint': endpoint, 'hostname': primary, 'aliases': aliases})
        callbacks.append({'project': project, 'endpoint': endpoint,
                          'urls': ['https://' + primary + path for path in contract['callbacks']],
                          'auth_contract': copy.deepcopy(contract.get('access', contract.get('application_auth')))})
    for tunnel, rules in tunnels.items():
        tunnels[tunnel] = sorted(rules, key=lambda rule: rule['hostname']) + [{'service': 'http_status:404'}]
    return {'bindings': sorted(normalized, key=lambda b: (b['project'], b['endpoint'])),
            'tunnels': tunnels, 'callbacks': sorted(callbacks, key=lambda item: (item['project'], item['endpoint'])), 'policy_sha256': digest(policy)}


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def read_json(path):
    path = Path(path).expanduser().absolute()
    require(path.resolve() == path, 'SYMLINK_FORBIDDEN')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                and info.st_mode & 0o077 == 0 and info.st_size <= 1_000_000, 'PRIVATE_FILE_REQUIRED')
        raw = stream.read(1_000_001)
        require(len(raw) <= 1_000_000, 'PRIVATE_FILE_TOO_LARGE')
        return json.loads(raw, object_pairs_hook=unique_pairs,
                          parse_constant=lambda value: require(False, 'INVALID_JSON_NUMBER'))


def private_dir(path):
    path = Path(path).expanduser().absolute()
    require(path.resolve() == path, 'SYMLINK_FORBIDDEN')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0, 'PRIVATE_DIRECTORY_REQUIRED')
    return path


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def sync_dir(path):
    directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class Store:
    def __init__(self, path):
        self.root = private_dir(path)
        self.revisions = private_dir(self.root / 'revisions')

    def current(self):
        pointer = self.root / 'desired.json'
        if not pointer.exists():
            require(not pointer.is_symlink(), 'SYMLINK_FORBIDDEN')
            return None
        value = read_json(pointer)
        keys(value, ('revision',))
        self.load(value['revision'])
        return value['revision']

    def load(self, revision):
        require(isinstance(revision, str) and REVISION.fullmatch(revision), 'INVALID_REVISION')
        data = read_json(self.revisions / (revision + '.json'))
        require(isinstance(data, dict) and digest(data) == revision and data.get('schema') == SCHEMA, 'REVISION_CHANGED')
        return data

    def prepare(self, policy, bindings, expected):
        compiled = compile_bindings(policy, bindings)
        fd = os.open(self.root / 'operation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'r+') as lock:
            info = os.fstat(lock.fileno())
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0, 'PRIVATE_LOCK_REQUIRED')
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DomainError('STATE_BUSY') from None
            current = self.current()
            require(current == expected, 'REVISION_CONFLICT')
            if current is not None:
                existing = self.load(current)
                if all(existing.get(key) == value for key, value in compiled.items()):
                    return current
            data = {'schema': SCHEMA, 'status': 'DESIRED_ONLY', 'previous': current, **compiled}
            revision = digest(data)
            target = self.revisions / (revision + '.json')
            if target.exists():
                require(self.load(revision) == data, 'REVISION_CHANGED')
            else:
                write_new(target, data)
            sync_dir(self.revisions)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(canonical({'revision': revision}) + b'\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.root / 'desired.json')
                sync_dir(self.root)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return revision

    def switch(self, policy, project, endpoint, new_hostname, expected, keep_old=True):
        require(expected is not None and self.current() == expected, 'REVISION_CONFLICT')
        bindings = self.load(expected)['bindings']
        matches = [b for b in bindings if b['project'] == project and b['endpoint'] == endpoint]
        require(len(matches) == 1, 'BINDING_NOT_FOUND')
        binding = matches[0]
        old = binding['hostname']
        binding['hostname'] = hostname(new_hostname)
        binding['aliases'] = list(set(binding['aliases'] + [old])) if keep_old else []
        return self.prepare(policy, bindings, expected)

    def rollback(self, policy, revision, expected):
        # Revalidate historic bindings under today's policy, not historic trust.
        return self.prepare(policy, self.load(revision)['bindings'], expected)

    def export(self, policy, revision, output):
        data = self.load(revision)
        compiled = compile_bindings(policy, data['bindings'])
        require(all(data[key] == value for key, value in compiled.items()), 'POLICY_CHANGED_REPREPARE')
        output = Path(output).expanduser().absolute()
        require(output.resolve() == output and not output.exists(), 'FRESH_OUTPUT_REQUIRED')
        output.mkdir(mode=0o700)
        for tunnel, ingress in compiled['tunnels'].items():
            write_new(output / (tunnel + '.ingress.json'), {'ingress': ingress})
        write_new(output / 'plan.json', {**data, 'revision': revision,
            'live_status': 'NOT_VERIFIED',
            'required_live_readback': ['domain_owner', 'existing_tunnel_rules', 'dns', 'tls_waf_rate_limits',
                                      'access_or_application_auth', 'vpn_origin_reachability', 'callbacks', 'rollback']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'switch', 'rollback', 'export', 'status'))
    parser.add_argument('--state', required=True, help='Private local desired-state directory')
    parser.add_argument('--policy', help='Private owner/project/zone/origin contract JSON')
    parser.add_argument('--routes', help='Private bindings JSON: schema and bindings')
    parser.add_argument('--expect', help='Expected desired revision, or none on first prepare')
    parser.add_argument('--revision')
    parser.add_argument('--project')
    parser.add_argument('--endpoint')
    parser.add_argument('--hostname')
    parser.add_argument('--remove-old', action='store_true', help='Do not retain previous host aliases in the desired plan')
    parser.add_argument('--output')
    args = parser.parse_args()
    try:
        store = Store(args.state)
        if args.action == 'status':
            revision = store.current()
        else:
            require(args.policy, 'POLICY_REQUIRED')
            policy = read_json(args.policy)
            expected = None if args.expect == 'none' else args.expect
            if args.action in ('prepare', 'switch', 'rollback'):
                require(args.expect is not None, 'EXPECTED_REVISION_REQUIRED')
            if args.action == 'prepare':
                require(args.routes, 'ROUTES_REQUIRED')
                routes = read_json(args.routes)
                keys(routes, ('schema', 'bindings'))
                require(routes['schema'] == SCHEMA, 'INVALID_SCHEMA')
                revision = store.prepare(policy, routes['bindings'], expected)
            elif args.action == 'switch':
                revision = store.switch(policy, args.project, args.endpoint, args.hostname, expected, not args.remove_old)
            elif args.action == 'rollback':
                revision = store.rollback(policy, args.revision, expected)
            else:
                require(args.output, 'OUTPUT_REQUIRED')
                revision = args.revision or store.current()
                store.export(policy, revision, args.output)
        print('DOMAIN_DESIRED_REVISION=' + (revision or 'NONE'))
        print('DOMAIN_LIVE_STATUS=NOT_VERIFIED')
        return 0
    except (DomainError, OSError, ValueError, TypeError, KeyError) as exc:
        print('DOMAIN_CONFIG_ERROR=' + (str(exc) if isinstance(exc, DomainError) else type(exc).__name__))
        print('DOMAIN_CONFIG=FAIL')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
