#!/usr/bin/env python3
"""Render and start a guarded, disposable VPN protection group; never redeploy Core.

No raw profile values, Docker diagnostics or packet addresses are printed. Generated
bundles are private local state, not source or evidence of successful VPN protection.
"""
import argparse
import base64
import configparser
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

REGIONS = {'jp': 'Windscribe-Tokyo-Shinkansen-WG.conf',
           'kr': 'Windscribe-Seoul-Hangang-WG.conf'}
IMAGE = re.compile(r'(?:sha256:[a-f0-9]{64}|[a-zA-Z0-9./_-]+@sha256:[a-f0-9]{64})\Z')
PROJECT = re.compile(r'gace-vpn-[a-f0-9]{16}\Z')
SOCKET = 'unix:///var/run/docker.sock'
GUARD = 'gserver_privacy'


# Executed only through the caller's existing sudo authority. Opening the netns
# here avoids requiring an unprivileged controller to stat root-owned PIDs.
NAMESPACE_HELPER = r"""
import json,os,subprocess,sys
fd=None
try:
 mode,pid=sys.argv[1],int(sys.argv[2])
 if mode not in ('install','inspect') or pid<=1:
  raise ValueError('INVALID_NAMESPACE_REQUEST')
 fd=os.open('/proc/'+str(pid)+'/ns/net',os.O_RDONLY)
 inode=os.fstat(fd).st_ino
 if inode==os.stat('/proc/1/ns/net').st_ino:
  raise ValueError('HOST_NAMESPACE_FORBIDDEN')
 command=['nsenter','--net=/proc/self/fd/'+str(fd),'nft']
 if mode=='install':
  subprocess.run(command+['-f',sys.argv[3]],pass_fds=(fd,),check=True,capture_output=True,text=True,timeout=20)
 result=subprocess.run(command+['-j','list','table','inet','gserver_privacy'],pass_fds=(fd,),check=True,capture_output=True,text=True,timeout=20)
 print(json.dumps({'ok':True,'inode':inode,'nft':json.loads(result.stdout)}))
except (OSError,ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
 code='HOST_NAMESPACE_FORBIDDEN' if str(exc)=='HOST_NAMESPACE_FORBIDDEN' else 'NAMESPACE_GUARD_COMMAND_FAILED'
 if isinstance(exc,PermissionError):code='NAMESPACE_PERMISSION_DENIED'
 if isinstance(exc,FileNotFoundError):code='NAMESPACE_TOOL_OR_PID_MISSING'
 if isinstance(exc,subprocess.CalledProcessError):code='NFT_COMMAND_FAILED'
 if isinstance(exc,subprocess.TimeoutExpired):code='NAMESPACE_COMMAND_TIMEOUT'
 diagnostic=exc.stderr if isinstance(exc,subprocess.CalledProcessError) else ''
 print(json.dumps({'ok':False,'code':code,'diagnostic':diagnostic or ''}))
finally:
 if fd is not None:os.close(fd)
"""


class VPNError(Exception):
    def __init__(self, code, diagnostic=''):
        super().__init__(code)
        self.diagnostic = diagnostic



def private_read(path, limit=32768):
    """Read bounded owner-only regular files without following the final link."""
    path = Path(path).expanduser().absolute()
    try:
        if path.resolve() != path:
            raise VPNError('PRIVATE_FILE_SYMLINK')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid() or info.st_nlink != 1:
                raise VPNError('PRIVATE_FILE_PERMISSIONS')
            data = os.read(fd, limit + 1)
            if not 0 < len(data) <= limit:
                raise VPNError('PRIVATE_FILE_SIZE')
            return path, data
        finally:
            os.close(fd)
    except OSError as exc:
        raise VPNError('PRIVATE_FILE_UNAVAILABLE') from exc


def profile(path, region):
    if region not in REGIONS:
        raise VPNError('REGION_INVALID')
    path, data = private_read(path)
    if path.name != REGIONS[region]:
        raise VPNError('PROFILE_REGION_FILENAME')
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    try:
        config.read_string(data.decode('ascii'))
        if config.defaults() or set(config.sections()) != {'Interface', 'Peer'}:
            raise ValueError()
        interface, peer = config['Interface'], config['Peer']
        if set(interface) - {'PrivateKey', 'Address', 'DNS', 'MTU'} or set(peer) - {'PublicKey', 'PresharedKey', 'AllowedIPs', 'Endpoint', 'PersistentKeepalive'}:
            raise ValueError()
        for section, key in ((interface, 'PrivateKey'), (peer, 'PublicKey')):
            if len(base64.b64decode(section[key], validate=True)) != 32:
                raise ValueError()
        if 'PresharedKey' in peer and len(base64.b64decode(peer['PresharedKey'], validate=True)) != 32:
            raise ValueError()
        addresses = [ipaddress.ip_interface(x.strip()) for x in interface['Address'].split(',')]
        if not addresses or not any(x.version == 4 for x in addresses):
            raise ValueError()
        dns = [ipaddress.ip_address(x.strip()) for x in interface['DNS'].split(',')]
        if not dns or any(x.version != 4 or x.is_loopback or x.is_unspecified or x.is_multicast or x.is_link_local for x in dns):
            raise ValueError()
        ips = {str(ipaddress.ip_network(x.strip(), strict=False)) for x in peer['AllowedIPs'].split(',')}
        if '0.0.0.0/0' not in ips or ips - {'0.0.0.0/0', '::/0'}:
            raise ValueError()
        host, port = peer['Endpoint'].rsplit(':', 1)
        if not 1 <= int(port) <= 65535:
            raise ValueError()
        try:
            endpoint = ipaddress.ip_address(host)
            if endpoint.version != 4 or not endpoint.is_global:
                raise ValueError()
            host = str(endpoint)
        except ValueError:
            if len(host) > 253 or not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z][A-Za-z0-9-]{0,62}', host):
                raise ValueError()

        if 'MTU' in interface and not 1280 <= int(interface['MTU']) <= 1500:
            raise ValueError()
        if 'PersistentKeepalive' in peer and not 0 <= int(peer['PersistentKeepalive']) <= 600:
            raise ValueError()
    except (ValueError, KeyError, configparser.Error, UnicodeError) as exc:
        raise VPNError('PROFILE_INVALID_OR_UNSUPPORTED') from exc
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
            'endpoint': host, 'port': int(port), 'region': region}


def guard_rules(endpoint, port):
    # Input strings originate in the strict profile parser, never shell text.
    ip = ipaddress.ip_address(endpoint)
    if ip.version != 4 or not ip.is_global or not 1 <= int(port) <= 65535:
        raise VPNError('ENDPOINT_INVALID')
    return f'''table inet {GUARD} {{
 chain output {{
  type filter hook output priority -200; policy drop;
  ip daddr 127.0.0.11 udp dport 53 drop
  ip daddr 127.0.0.11 tcp dport 53 drop
  oifname "lo" ip daddr 127.0.0.0/8 accept
  oifname "tun0" meta nfproto ipv4 accept
  oifname "eth0" ip daddr {ip} udp dport {int(port)} accept
  counter drop
 }}
}}
'''


def pinned(image):
    if not IMAGE.fullmatch(image):
        raise VPNError('IMMUTABLE_IMAGE_REQUIRED')
    return image


def render(directory, region, source, vpn_image, app_image, endpoint_ip=None):
    p = profile(source, region)
    try:
        selected = ipaddress.ip_address(endpoint_ip or p['endpoint'])
        if selected.version != 4 or not selected.is_global:
            raise ValueError()
    except ValueError as exc:
        raise VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED') from exc
    # No hostname resolution is performed. A provider hostname requires an
    # explicit pinned address; the peer key is still verified by WireGuard.
    _, raw = private_read(p['path'])
    if hashlib.sha256(raw).hexdigest() != p['sha256']:
        raise VPNError('PROFILE_CHANGED')
    runtime = configparser.ConfigParser(interpolation=None)
    runtime.optionxform = str
    runtime.read_string(raw.decode('ascii'))
    runtime['Interface']['Address'] = ', '.join(x.strip() for x in runtime['Interface']['Address'].split(',') if ipaddress.ip_interface(x.strip()).version == 4)
    runtime['Peer']['AllowedIPs'] = '0.0.0.0/0'
    runtime['Peer']['Endpoint'] = str(selected) + ':' + str(p['port'])
    import io
    stream = io.StringIO()
    runtime.write(stream)
    pinned(vpn_image)
    pinned(app_image)
    directory = Path(directory).expanduser().absolute()
    if directory.resolve() != directory:
        raise VPNError('BUNDLE_SYMLINK')
    # A fresh directory prevents overwriting an installed release or secret.
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    name = 'gace-vpn-' + secrets.token_hex(8)
    log = {'driver': 'local', 'options': {'max-size': '1m', 'max-file': '2'}}
    shared = {'restart': 'no', 'read_only': True, 'cap_drop': ['ALL'],
              'security_opt': ['no-new-privileges:true'], 'pids_limit': 96,
              'mem_limit': '256m', 'cpus': '1.0', 'logging': log}
    config = {'name': name, 'services': {
        'vpn': {**shared, 'image': vpn_image, 'pull_policy': 'never', 'user': '0:0',
            'cap_add': ['NET_ADMIN'], 'devices': ['/dev/net/tun:/dev/net/tun'],
            'sysctls': {'net.ipv6.conf.all.disable_ipv6': '1', 'net.ipv6.conf.default.disable_ipv6': '1'},
            'entrypoint': ['/bin/sh', '-ec', 'while [ ! -f /run/gserver-guard/ready ]; do sleep 1; done; exec /gluetun-entrypoint'],
            'environment': {'VPN_SERVICE_PROVIDER': 'custom', 'VPN_TYPE': 'wireguard',
                'VPN_INTERFACE': 'tun0', 'FIREWALL': 'on', 'HTTPPROXY': 'off',
                'SHADOWSOCKS': 'off', 'LOG_LEVEL': 'warn'},
            'tmpfs': ['/tmp:rw,noexec,nosuid,nodev,size=16m', '/gluetun:rw,nosuid,nodev,size=16m',
                      '/run/gserver-guard:rw,noexec,nosuid,nodev,size=1m,mode=0700'],
            'healthcheck': {'test': ['CMD', '/gluetun-entrypoint', 'healthcheck'],
                            'interval': '10s', 'timeout': '5s', 'retries': 6}},
        'app': {**shared, 'image': app_image, 'pull_policy': 'never', 'user': '65534:65534',
            'network_mode': 'service:vpn', 'depends_on': {'vpn': {'condition': 'service_healthy'}},
            'configs': [{'source': 'vpn_dns', 'target': '/etc/resolv.conf'}],
            'tmpfs': ['/tmp:rw,noexec,nosuid,nodev,size=16m,uid=65534,gid=65534,mode=0700']}},
        'configs': {'vpn_dns': {'content': 'nameserver 127.0.0.1\noptions timeout:2 attempts:2\n'}}}
    contents = {'compose.json': json.dumps(config, indent=2) + '\n',
                'guard.nft': guard_rules(str(selected), p['port']),
                'wireguard.conf': stream.getvalue()}
    manifest = {'schema': 'gserver.vpn-bundle.v1', 'project': name,
                'profile': {'path': p['path'], 'region': region, 'sha256': p['sha256']},
                'hashes': {key: hashlib.sha256(value.encode()).hexdigest() for key, value in contents.items()},
                'acceptance': {key: 'NOT_VERIFIED' for key in ('IP', 'NET', 'INGRESS', 'CRYPTO', 'RESPONSE', 'PERFORMANCE', 'OPS')}}
    contents['manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    for key, value in contents.items():
        fd = os.open(directory / key, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
    return manifest


def load(directory):
    directory = Path(directory).expanduser().absolute()
    if directory.resolve() != directory or directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.geteuid():
        raise VPNError('BUNDLE_PERMISSIONS')
    _, data = private_read(directory / 'manifest.json')
    try:
        manifest = json.loads(data)
        if manifest['schema'] != 'gserver.vpn-bundle.v1' or not PROJECT.fullmatch(manifest['project']):
            raise ValueError()
        if set(manifest['hashes']) != {'compose.json', 'guard.nft', 'wireguard.conf'}:
            raise ValueError()
        for name, digest in manifest['hashes'].items():
            _, raw = private_read(directory / name)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError()
        current = profile(manifest['profile']['path'], manifest['profile']['region'])
        if current['sha256'] != manifest['profile']['sha256']:
            raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise VPNError('BUNDLE_OR_PROFILE_CHANGED') from exc
    return directory, manifest


def run(cmd, input=None):
    try:
        result = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VPNError('LOCAL_COMMAND_FAILED') from exc
    if result.returncode:
        raise VPNError('LOCAL_COMMAND_FAILED')
    return result.stdout


def namespace_guard(pid, rules=None):
    privilege = [] if os.geteuid() == 0 else ['sudo', '-n']
    mode = 'install' if rules is not None else 'inspect'
    cmd = privilege + ['python3', '-c', NAMESPACE_HELPER, mode, str(pid)]
    if rules is not None:
        cmd.append(str(rules))
    try:
        result = json.loads(run(cmd))
        if not isinstance(result, dict):
            raise ValueError()
        if result.get('ok') is not True:
            code = result.get('code', 'NAMESPACE_GUARD_COMMAND_FAILED')
            if not isinstance(code,str) or not re.fullmatch(r'[A-Z_]{1,64}',code):
                code = 'NAMESPACE_GUARD_COMMAND_FAILED'
            raise VPNError(code, diagnostic=result.get('diagnostic',''))
        if not isinstance(result.get('inode'), int) or not isinstance(result.get('nft'), dict):
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise VPNError('NAMESPACE_REPORT_INVALID') from exc
    return result


def policy_fingerprint(report):
    # Counters change with packets; rule semantics must remain identical.
    def clean(value):
        if isinstance(value, dict):
            return {k: (0 if k in ('packets', 'bytes') else clean(v))
                    for k, v in value.items() if k not in ('handle', 'metainfo')}
        if isinstance(value, list):
            return [clean(v) for v in value if not isinstance(v, dict) or 'metainfo' not in v]
        return value
    return hashlib.sha256(json.dumps(clean(report['nft']),sort_keys=True).encode()).hexdigest()


def start(directory):
    directory, manifest = load(directory)
    privilege = [] if os.geteuid() == 0 else ['sudo', '-n']
    docker = privilege + ['docker', '--host', SOCKET]
    compose = docker + ['compose', '--project-name', manifest['project'], '--env-file', '/dev/null',
                        '--project-directory', str(directory), '-f', str(directory / 'compose.json')]
    if run(docker + ['ps', '-aq', '--filter', 'label=com.docker.compose.project=' + manifest['project']]).strip():
        raise VPNError('PROJECT_EXISTS_REFUSE_ADOPTION')
    existing_networks = run(docker + ['network', 'ls', '--format', '{{.Name}}']).splitlines()
    if manifest['project'] + '_default' in existing_networks:
        raise VPNError('NETWORK_EXISTS_REFUSE_ADOPTION')
    # Resolve all local images before creating anything; no registry access.
    config = json.loads((directory / 'compose.json').read_text())
    for service in config['services'].values():
        run(docker + ['image', 'inspect', pinned(service['image'])])
    created = False
    try:
        created = True
        run(compose + ['up', '-d', '--no-build', '--pull', 'never', 'vpn'])
        ids = run(compose + ['ps', '-q', 'vpn']).split()
        if len(ids) != 1:
            raise VPNError('VPN_CONTAINER_MISSING')
        info = json.loads(run(docker + ['inspect', ids[0]]))[0]
        pid = info['State']['Pid']
        if not isinstance(pid, int) or pid <= 1 or info['Config']['Labels']['com.docker.compose.project'] != manifest['project']:
            raise VPNError('VPN_NAMESPACE_INVALID')
        initial = namespace_guard(pid, directory / 'guard.nft')
        # Refuse PID/container restart between guard installation and release.
        after = json.loads(run(docker + ['inspect', ids[0]]))[0]
        current = namespace_guard(pid)
        if after['State']['Pid'] != pid or current['inode'] != initial['inode']:
            raise VPNError('VPN_NAMESPACE_CHANGED')
        _, wireguard = private_read(directory / 'wireguard.conf')
        run(docker + ['exec', '-i', ids[0], '/bin/sh', '-ec',
                     'umask 077; mkdir -p /gluetun/wireguard; cat > /gluetun/wireguard/wg0.conf'],
            input=wireguard.decode('ascii'))
        run(docker + ['exec', ids[0], '/bin/sh', '-ec', 'touch /run/gserver-guard/ready'])
        ready = ['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '90']
        run(compose + ready + ['vpn'])
        # Verify independent guard survived the VPN's own firewall setup before
        # giving any application access to this network namespace.
        current = namespace_guard(pid)
        if current['inode'] != initial['inode'] or policy_fingerprint(current) != policy_fingerprint(initial):
            raise VPNError('VPN_GUARD_CHANGED_DURING_BOOTSTRAP')
        run(compose + ready + ['app'])
    except BaseException:
        if created:
            try:
                run(compose + ['stop', '--timeout', '10'])
            except VPNError:
                raise VPNError('START_FAILED_STOP_NOT_VERIFIED') from None
        raise
    # A healthy container is explicitly not leak/performance/Telegram acceptance.
    return 'STARTED_ACCEPTANCE_NOT_VERIFIED'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    check = sub.add_parser('verify')
    check.add_argument('region', choices=REGIONS)
    check.add_argument('profile')
    create = sub.add_parser('render')
    create.add_argument('region', choices=REGIONS)
    create.add_argument('profile')
    create.add_argument('--vpn-image', required=True)
    create.add_argument('--app-image', required=True)
    create.add_argument('--output', required=True)
    create.add_argument('--endpoint-ip', help='Explicit verified public IPv4 pin; no automatic DNS bootstrap')
    launch = sub.add_parser('start')
    launch.add_argument('directory')
    args = parser.parse_args()
    try:
        if args.action == 'verify':
            profile(args.profile, args.region)
            print('VPN_PROFILE_STRUCTURE=PASS;CONNECTION=NOT_VERIFIED')
        elif args.action == 'render':
            render(args.output, args.region, args.profile, args.vpn_image, args.app_image, args.endpoint_ip)
            print('VPN_BUNDLE=CREATED_PRIVATE;RUNTIME=NOT_VERIFIED')
        else:
            print('VPN_RUNTIME=' + start(args.directory))
    except (VPNError, OSError, ValueError, KeyError, TypeError):
        # Never stringify parser, file or subprocess exceptions containing keys.
        print('VPN_OPERATION=FAIL;DETAILS=WITHHELD', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
