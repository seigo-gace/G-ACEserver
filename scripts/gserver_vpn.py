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
ENDPOINT_CACHE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'gserver/vpn-profiles/endpoint-cache.json'
TUNNEL_CREDENTIAL = 'cloudflared.credential'
CLOUDFLARED_WAIT = ('while [ ! -f /run/gserver-guard/ready ]; do sleep 1; done; '
                    'while [ ! -f /run/gserver-tunnel/credential ]; do sleep 3600; done; '
                    'exec cloudflared tunnel --no-autoupdate run --token "$(cat /run/gserver-tunnel/credential)"')


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


def write_endpoint_pin(region, address):
    """Persist a single public IPv4 endpoint pin in owner-only local state."""
    if region not in REGIONS:
        raise VPNError('REGION_INVALID')
    try:
        selected = ipaddress.ip_address(str(address).strip())
        if selected.version != 4 or not selected.is_global:
            raise ValueError()
    except ValueError as exc:
        raise VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED') from exc
    ENDPOINT_CACHE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = {}
    if ENDPOINT_CACHE.is_file():
        _, data = private_read(ENDPOINT_CACHE)
        try:
            loaded = json.loads(data)
            if isinstance(loaded, dict):
                cache = loaded
        except (ValueError, TypeError) as exc:
            raise VPNError('ENDPOINT_CACHE_INVALID') from exc
    cache[region] = str(selected)
    payload = (json.dumps(cache, indent=2, sort_keys=True) + '\n').encode('ascii')
    tmp = ENDPOINT_CACHE.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        os.close(fd)
        raise VPNError('ENDPOINT_CACHE_WRITE_FAILED') from None
    os.replace(tmp, ENDPOINT_CACHE)
    ENDPOINT_CACHE.chmod(0o600)
    return 'ENDPOINT_PIN_SAVED'


def endpoint_pins():
    """Read owner-maintained IPv4 pins; never print addresses or write to Git."""
    if not ENDPOINT_CACHE.is_file():
        return {}
    _, data = private_read(ENDPOINT_CACHE)
    try:
        cache = json.loads(data)
        if not isinstance(cache, dict):
            raise ValueError()
        pins = {}
        for region in REGIONS:
            if region not in cache:
                continue
            value = cache[region]
            if isinstance(value, list):
                if not value:
                    continue
                if len(value) != 1:
                    raise ValueError()
                value = value[0]
            if not isinstance(value, str) or not value.strip():
                continue
            address = ipaddress.ip_address(value.strip())
            if address.version != 4 or not address.is_global:
                raise ValueError()
            pins[region] = str(address)
        return pins
    except (ValueError, TypeError) as exc:
        raise VPNError('ENDPOINT_CACHE_INVALID') from exc


def inspect_local_image(image, privilege):
    pinned(image)
    try:
        run(privilege + ['docker', '--host', SOCKET, 'image', 'inspect', image])
    except VPNError as exc:
        raise VPNError('LOCAL_PINNED_IMAGE_MISSING') from exc
    return 'LOCAL_PINNED_IMAGE_PRESENT'


def docker_access(privilege):
    try:
        if privilege:
            run(privilege + ['-n', 'true'])
        run(privilege + ['docker', '--host', SOCKET, 'info'], timeout=30)
    except VPNError:
        return 'DOCKER_SUDO_AUTH_REQUIRED'
    return 'OK'


def local_image_status(image, privilege):
    try:
        pinned(image)
    except VPNError:
        return 'IMMUTABLE_IMAGE_REQUIRED'
    try:
        run(privilege + ['docker', '--host', SOCKET, 'image', 'inspect', image])
    except VPNError:
        return 'LOCAL_PINNED_IMAGE_MISSING'
    return 'LOCAL_PINNED_IMAGE_PRESENT'


def preflight(vpn_image, app_image=None, cloudflared_image=None):
    privilege = [] if os.geteuid() == 0 else ['sudo']
    status = {'docker_access': docker_access(privilege)}
    status['vpn'] = local_image_status(vpn_image, privilege)
    if app_image:
        status['app'] = local_image_status(app_image, privilege)
    if cloudflared_image:
        status['cloudflared'] = local_image_status(cloudflared_image, privilege)
    for region in REGIONS:
        status['endpoint_pin_' + region] = 'NOT_CONFIGURED'
    if ENDPOINT_CACHE.is_file():
        try:
            pins = endpoint_pins()
            status['endpoint_cache'] = 'OK'
            for region in pins:
                status['endpoint_pin_' + region] = 'CONFIGURED'
        except VPNError:
            status['endpoint_cache'] = 'INVALID'
    else:
        status['endpoint_cache'] = 'MISSING'
    return status


def hints():
    """Non-secret local inventory hints for building pinned image references."""
    privilege = [] if os.geteuid() == 0 else ['sudo']
    if docker_access(privilege) != 'OK':
        return {'docker_access': 'DOCKER_SUDO_AUTH_REQUIRED'}
    out = {'docker_access': 'OK'}
    core = 'gace-gserver-gserver-1'
    try:
        raw = run(privilege + ['docker', '--host', SOCKET, 'inspect', core, '--format', '{{.Image}}'])
        image = raw.strip()
        if IMAGE.fullmatch(image):
            out['core_app_image'] = image
        elif re.fullmatch(r'sha256:[a-f0-9]{64}', image):
            out['core_app_image'] = image
        else:
            out['core_app_image'] = 'UNPINNED_LOCAL_ID'
    except VPNError:
        out['core_app_image'] = 'CORE_CONTAINER_NOT_FOUND'
    try:
        lines = run(privilege + ['docker', '--host', SOCKET, 'images', '--digests', '--format',
                                 '{{.Repository}}@{{.Digest}}']).splitlines()
        for name in ('gluetun', 'cloudflared'):
            matches = [line for line in lines if line.startswith('qmcgaw/' + name + '@sha256:')
                       or line.startswith('cloudflare/' + name + '@sha256:')
                       or line.startswith('passteque/' + name + '@sha256:')]
            out[name + '_candidates'] = str(len(matches))
            if len(matches) == 1:
                out['suggested_' + name + '_image'] = matches[0]
            elif not matches:
                out['suggested_' + name + '_image'] = 'LOCAL_PINNED_IMAGE_MISSING'
    except VPNError:
        out['image_list'] = 'UNAVAILABLE'
    return out


def render_endpoint_ip(region, profile_endpoint, endpoint_ip=None):
    if endpoint_ip:
        candidate = endpoint_ip
    else:
        pins = endpoint_pins()
        candidate = pins.get(region) or profile_endpoint
    try:
        selected = ipaddress.ip_address(candidate)
        if selected.version != 4 or not selected.is_global:
            raise ValueError()
    except ValueError as exc:
        raise VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED') from exc
    return str(selected)


def render(directory, region, source, vpn_image, app_image, endpoint_ip=None, cloudflared_image=None):
    p = profile(source, region)
    selected = render_endpoint_ip(region, p['endpoint'], endpoint_ip)
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
    runtime['Peer']['Endpoint'] = selected + ':' + str(p['port'])
    import io
    stream = io.StringIO()
    runtime.write(stream)
    pinned(vpn_image)
    pinned(app_image)
    if cloudflared_image:
        pinned(cloudflared_image)
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
            'healthcheck': {'test': ['CMD', '/bin/sh', '-ec',
                '[ -f /run/gserver-guard/ready ] || exit 0; exec /gluetun-entrypoint healthcheck'],
                            'interval': '10s', 'timeout': '5s', 'retries': 12, 'start_period': '30s'}},
        'app': {**shared, 'image': app_image, 'pull_policy': 'never', 'user': '65534:65534',
            'network_mode': 'service:vpn', 'depends_on': {'vpn': {'condition': 'service_healthy'}},
            'configs': [{'source': 'vpn_dns', 'target': '/etc/resolv.conf'}],
            'tmpfs': ['/tmp:rw,noexec,nosuid,nodev,size=16m,uid=65534,gid=65534,mode=0700']}},
        'configs': {'vpn_dns': {'content': 'nameserver 127.0.0.1\noptions timeout:2 attempts:2\n'}}}
    if cloudflared_image:
        config['services']['cloudflared'] = {**shared, 'image': cloudflared_image, 'pull_policy': 'never',
            'user': '65534:65534', 'network_mode': 'service:vpn',
            'depends_on': {'vpn': {'condition': 'service_healthy'}},
            'entrypoint': ['/bin/sh', '-ec', CLOUDFLARED_WAIT],
            'tmpfs': ['/tmp:rw,noexec,nosuid,nodev,size=16m,uid=65534,gid=65534,mode=0700',
                      '/run/gserver-tunnel:rw,noexec,nosuid,nodev,size=1m,mode=0700,uid=65534,gid=65534']}
    contents = {'compose.json': json.dumps(config, indent=2) + '\n',
                'guard.nft': guard_rules(selected, p['port']),
                'wireguard.conf': stream.getvalue()}
    manifest = {'schema': 'gserver.vpn-bundle.v1', 'project': name,
                'profile': {'path': p['path'], 'region': region, 'sha256': p['sha256']},
                'components': sorted(config['services']),
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


def sanitize_diagnostic(text, limit=512):
    if not text:
        return ''
    cleaned = re.sub(r'[\x00-\x1f\x7f]', ' ', str(text))
    cleaned = re.sub(r'[A-Za-z0-9_+/=-]{32,}', '<redacted>', cleaned)
    cleaned = re.sub(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '<ip>', cleaned)
    cleaned = re.sub(r'(PrivateKey|PresharedKey|Bearer|token=)\S*', r'\1<redacted>', cleaned, flags=re.I)
    return cleaned[:limit].strip()


def run(cmd, input=None, timeout=180, *, step=''):
    try:
        result = subprocess.run(cmd, input=input, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VPNError('LOCAL_COMMAND_FAILED', diagnostic=step or type(exc).__name__) from exc
    if result.returncode:
        detail = sanitize_diagnostic(((result.stderr or '') + '\n' + (result.stdout or '')).strip())
        diagnostic = (step + ': ' + detail) if step and detail else (step or detail or 'nonzero_exit')
        raise VPNError('LOCAL_COMMAND_FAILED', diagnostic=diagnostic)
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
        run(compose + ['up', '-d', '--no-build', '--pull', 'never', 'vpn'], step='compose_up_vpn_bootstrap')
        ids = run(compose + ['ps', '-q', 'vpn'], step='compose_ps_vpn').split()
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
            input=wireguard.decode('ascii'), step='docker_exec_wireguard_conf')
        run(docker + ['exec', ids[0], '/bin/sh', '-ec', 'touch /run/gserver-guard/ready'],
            step='docker_exec_guard_ready')
        ready = ['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '120']
        run(compose + ready + ['vpn'], step='compose_up_vpn_wait_healthy', timeout=150)
        # Verify independent guard survived the VPN's own firewall setup before
        # giving any application access to this network namespace.
        current = namespace_guard(pid)
        if current['inode'] != initial['inode'] or policy_fingerprint(current) != policy_fingerprint(initial):
            raise VPNError('VPN_GUARD_CHANGED_DURING_BOOTSTRAP')
        if 'cloudflared' in config['services']:
            credential = directory / TUNNEL_CREDENTIAL
            if not credential.is_file():
                raise VPNError('CLOUDFLARED_CREDENTIAL_MISSING')
            run(compose + ['up', '-d', '--no-build', '--pull', 'never', 'cloudflared'])
            tunnel_ids = run(compose + ['ps', '-q', 'cloudflared']).split()
            if len(tunnel_ids) != 1:
                raise VPNError('CLOUDFLARED_CONTAINER_MISSING')
            _, token = private_read(credential, limit=8192)
            if not token.strip():
                raise VPNError('CLOUDFLARED_CREDENTIAL_EMPTY')
            run(docker + ['exec', '-i', tunnel_ids[0], '/bin/sh', '-ec',
                           'umask 077; cat > /run/gserver-tunnel/credential'], input=token.decode('ascii'))
        if 'app' in config['services']:
            run(compose + ready + ['app'], step='compose_up_app_wait_healthy', timeout=150)
    except BaseException:
        if created:
            try:
                run(compose + ['stop', '--timeout', '10'])
            except VPNError:
                raise VPNError('START_FAILED_STOP_NOT_VERIFIED') from None
        raise
    # A healthy container is explicitly not leak/performance/Telegram acceptance.
    return 'STARTED_ACCEPTANCE_NOT_VERIFIED'


def pull_reference_images(*, confirm=False):
    """One-time registry pull for digest pinning; never run without explicit confirmation."""
    if not confirm:
        raise VPNError('REGISTRY_PULL_NOT_CONFIRMED')
    privilege = [] if os.geteuid() == 0 else ['sudo', '-n']
    docker = privilege + ['docker', '--host', SOCKET]
    references = ('qmcgaw/gluetun:v3.41.3', 'cloudflare/cloudflared:latest')
    digests = {}
    for reference in references:
        run(docker + ['pull', reference], timeout=900)
        digest = run(docker + ['inspect', reference, '--format', '{{index .RepoDigests 0}}']).strip()
        if not digest:
            raise VPNError('LOCAL_PINNED_IMAGE_MISSING')
        digests[reference] = digest
    return digests


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
    create.add_argument('--cloudflared-image', help='Pinned local cloudflared image; tunnel token stays out of Compose')
    probe = sub.add_parser('preflight')
    probe.add_argument('--vpn-image', required=True)
    probe.add_argument('--app-image')
    probe.add_argument('--cloudflared-image')
    hint = sub.add_parser('hints')
    hint.help = 'List safe local image hints; never prints secrets or profile contents'
    pin = sub.add_parser('set-endpoint-pin')
    pin.add_argument('region', choices=REGIONS)
    pin.add_argument('address', help='Verified public IPv4 for the WireGuard peer endpoint')
    pull = sub.add_parser('pull-reference-images')
    pull.add_argument('--confirm-registry-pull', action='store_true',
                      help='Required flag; pulls Gluetun and cloudflared reference tags once')
    launch = sub.add_parser('start')
    launch.add_argument('directory')
    args = parser.parse_args()
    try:
        if args.action == 'verify':
            profile(args.profile, args.region)
            print('VPN_PROFILE_STRUCTURE=PASS;CONNECTION=NOT_VERIFIED')
        elif args.action == 'render':
            render(args.output, args.region, args.profile, args.vpn_image, args.app_image,
                   args.endpoint_ip, args.cloudflared_image)
            print('VPN_BUNDLE=CREATED_PRIVATE;RUNTIME=NOT_VERIFIED')
        elif args.action == 'preflight':
            status = preflight(args.vpn_image, args.app_image, args.cloudflared_image)
            print('VPN_PREFLIGHT=' + ';'.join(f'{key}={value}' for key, value in sorted(status.items())))
        elif args.action == 'hints':
            data = hints()
            print('VPN_HINTS=' + ';'.join(f'{key}={value}' for key, value in sorted(data.items())))
        elif args.action == 'set-endpoint-pin':
            print('VPN_' + write_endpoint_pin(args.region, args.address))
        elif args.action == 'pull-reference-images':
            digests = pull_reference_images(confirm=args.confirm_registry_pull)
            print('VPN_REFERENCE_IMAGES=' + ';'.join(f'{key}={value}' for key, value in sorted(digests.items())))
        else:
            print('VPN_RUNTIME=' + start(args.directory))
    except VPNError as exc:
        print('VPN_ERROR=' + str(exc), file=sys.stderr)
        if exc.diagnostic and re.fullmatch(r'[A-Z0-9_ \t\r\n:./-]{0,512}', exc.diagnostic):
            print('VPN_DIAGNOSTIC=' + exc.diagnostic[:512], file=sys.stderr)
        print('VPN_OPERATION=FAIL', file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        print('VPN_ERROR=INTERNAL', file=sys.stderr)
        print('VPN_OPERATION=FAIL', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
