#!/usr/bin/env python3
"""Isolated WireGuard egress acceptance; Cloudflare ingress is a separate gate."""
import contextlib
import io
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import gserver_apps as apps
import gserver_vpn as vpn
from smoke_gserver_apps_host import docker, inventory, storage, CORE, safe_runtime_error

PROFILE_ROOT = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'gserver/vpn-profiles'


# Fixed public diagnostic endpoints, requested only from the guarded app namespace.
TRACE_URLS = ('https://1.1.1.1/cdn-cgi/trace', 'https://www.cloudflare.com/cdn-cgi/trace')
TCP_CANARY = '1.1.1.1'


def app_json(container, code):
    # A failed docker exec must never count as a blocked network probe.
    try:
        value = json.loads(docker('exec', '-u', '65534:65534', container, 'python3', '-B', '-c', code))
    except (ValueError, TypeError) as exc:
        raise vpn.VPNError('APP_PROBE_REPORT_INVALID') from exc
    if not isinstance(value, dict):
        raise vpn.VPNError('APP_PROBE_REPORT_INVALID')
    return value


def https_exit(container, url, region):
    if url not in TRACE_URLS:
        raise vpn.VPNError('EGRESS_TARGET_INVALID')
    code = (
        "import json,os,urllib.request\n"
        "class NoRedirect(urllib.request.HTTPRedirectHandler):\n"
        " def redirect_request(self,*a,**k): return None\n"
        "opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())\n"
        "with opener.open(" + repr(url) + ",timeout=12) as r:\n"
        " if r.status!=200: raise ValueError('HTTP_STATUS')\n"
        " data=r.read(4097)\n"
        " if len(data)>4096: raise ValueError('HTTP_BODY_TOO_LARGE')\n"
        " fields=dict(line.split('=',1) for line in data.decode('ascii').splitlines() if '=' in line)\n"
        "print(json.dumps({'uid':os.getuid(),'ip':fields.get('ip'),'country':fields.get('loc')}))\n"
    )
    result = app_json(container, code)
    try:
        address = ipaddress.ip_address(result['ip'])
    except (ValueError, TypeError, KeyError) as exc:
        raise vpn.VPNError('EGRESS_IP_INVALID') from exc
    if result.get('uid') != 65534 or address.version != 4 or not address.is_global:
        raise vpn.VPNError('EGRESS_IP_INVALID')
    if result.get('country') != {'jp': 'JP', 'kr': 'KR'}[region]:
        raise vpn.VPNError('EGRESS_COUNTRY_MISMATCH')
    return str(address)


def tcp_connected(container, address, port, *, ipv6=False):
    code = (
        "import errno,json,os,socket\n"
        "s=socket.socket(" + ('socket.AF_INET6' if ipv6 else 'socket.AF_INET') + ",socket.SOCK_STREAM)\n"
        "s.settimeout(3)\n"
        "try:\n s.connect((" + repr(address) + "," + str(port) + "));state='connected'\n"
        "except OSError as e:\n"
        " if not isinstance(e,TimeoutError) and e.errno not in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.EACCES,errno.EPERM,errno.EAFNOSUPPORT,errno.EADDRNOTAVAIL): raise\n"
        " state='blocked'\n"
        "finally:\n s.close()\n"
        "print(json.dumps({'uid':os.getuid(),'state':state}))\n"
    )
    result = app_json(container, code)
    if result.get('uid') != 65534 or result.get('state') not in ('connected', 'blocked'):
        raise vpn.VPNError('APP_PROBE_REPORT_INVALID')
    return result['state'] == 'connected'


def wireguard_state(container):
    # Never use dump/showconf/private-key: those include secret material.
    handshakes = docker('exec', container, 'wg', 'show', 'tun0', 'latest-handshakes').splitlines()
    transfers = docker('exec', container, 'wg', 'show', 'tun0', 'transfer').splitlines()
    try:
        if len(handshakes) != 1 or len(transfers) != 1:
            raise ValueError()
        peer, stamp = handshakes[0].split()
        other, rx, tx = transfers[0].split()
        stamp, rx, tx = int(stamp), int(rx), int(tx)
        if peer != other or not 0 <= time.time() - stamp <= 180 or min(rx, tx) < 0:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise vpn.VPNError('WIREGUARD_HANDSHAKE_OR_COUNTER_INVALID') from exc
    return peer, rx, tx


def app_guard(container):
    state = json.loads(docker('inspect', container))[0]['State']
    if not state.get('Running') or not isinstance(state.get('Pid'), int) or state['Pid'] <= 1:
        raise vpn.VPNError('APP_NOT_RUNNING')
    return vpn.namespace_guard(state['Pid'])


def unchanged_guard(before, after):
    if before['inode'] != after['inode'] or vpn.policy_fingerprint(before) != vpn.policy_fingerprint(after):
        raise vpn.VPNError('APP_NAMESPACE_OR_GUARD_CHANGED')


def dns_drop_packets(report, protocol):
    rules = [item['rule'] for item in report['nft'].get('nftables', [])
             if 'rule' in item and item['rule'].get('comment') == 'gserver_dns_' + protocol]
    if len(rules) != 1:
        raise vpn.VPNError('DNS_GUARD_COUNTER_MISSING')
    values = [expr['counter']['packets'] for expr in rules[0].get('expr', []) if 'counter' in expr]
    if len(values) != 1 or not isinstance(values[0], int):
        raise vpn.VPNError('DNS_GUARD_COUNTER_MISSING')
    return values[0]


def verify_network_guards(container):
    before = app_guard(container)
    if tcp_connected(container, '127.0.0.11', 53):
        raise vpn.VPNError('DOCKER_DNS_TCP_LEAK')
    result = app_json(container,
        "import json,os,socket\n"
        "s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(3)\n"
        "s.sendto(bytes.fromhex('123401000001000000000000076578616d706c6503636f6d0000010001'),('127.0.0.11',53))\n"
        "s.close()\nprint(json.dumps({'uid':os.getuid(),'sent':True}))\n")
    if result.get('uid') != 65534 or result.get('sent') is not True:
        raise vpn.VPNError('APP_PROBE_REPORT_INVALID')
    after = app_guard(container)
    unchanged_guard(before, after)
    for protocol in ('udp', 'tcp'):
        if dns_drop_packets(after, protocol) <= dns_drop_packets(before, protocol):
            raise vpn.VPNError('DNS_GUARD_DROP_NOT_OBSERVED')
    result = app_json(container,
        "import json,pathlib\nprint(json.dumps({'disabled':pathlib.Path('/proc/sys/net/ipv6/conf/all/disable_ipv6').read_text().strip()}))\n")
    if result.get('disabled') != '1' or tcp_connected(container, '2606:4700:4700::1111', 443, ipv6=True):
        raise vpn.VPNError('IPV6_NOT_BLOCKED')


def service_container(project, service):
    ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                 '--filter', 'label=com.docker.compose.service=' + service).split()
    if len(ids) != 1:
        raise vpn.VPNError('SERVICE_CONTAINER_MISSING')
    return ids[0]


def resolve_images():
    hints = vpn.hints()
    if hints.get('docker_access') != 'OK':
        raise vpn.VPNError('DOCKER_SUDO_AUTH_REQUIRED')
    app = hints.get('core_app_image')
    gluetun = hints.get('suggested_gluetun_image')
    tunnel = hints.get('suggested_cloudflared_image')
    if app in (None, 'CORE_CONTAINER_NOT_FOUND', 'UNPINNED_LOCAL_ID'):
        raise vpn.VPNError('APP_IMAGE_UNAVAILABLE')
    if gluetun == 'LOCAL_PINNED_IMAGE_MISSING':
        raise vpn.VPNError('LOCAL_PINNED_IMAGE_MISSING')
    vpn.pinned(app)
    vpn.pinned(gluetun)
    return app, gluetun, tunnel if tunnel != 'LOCAL_PINNED_IMAGE_MISSING' else None


def validate_live_preflight(status, region, *, require_cloudflared=False):
    """Require endpoint pin and images only for the selected VPN region."""
    if region not in vpn.REGIONS:
        raise vpn.VPNError('REGION_INVALID')
    pin_key = 'endpoint_pin_' + region
    if status.get(pin_key) == 'NOT_CONFIGURED':
        raise vpn.VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')
    for image_key in ('vpn', 'app'):
        if status.get(image_key) == 'LOCAL_PINNED_IMAGE_MISSING':
            raise vpn.VPNError('LOCAL_PINNED_IMAGE_MISSING')
    if require_cloudflared and status.get('cloudflared') == 'LOCAL_PINNED_IMAGE_MISSING':
        raise vpn.VPNError('LOCAL_PINNED_IMAGE_MISSING')


def verify_app_resolv_conf(container):
    """Confirm UID 65534 reads Config-mounted resolv.conf (VPN-local DNS, not Docker embedded)."""
    prefix = (['docker'] if apps.os.geteuid() == 0 else ['sudo', '-n', 'docker']) + ['--host', apps.DOCKER_SOCKET]
    vpn.verify_sidecar_resolv(prefix, container)


def assert_vpn_stop_blocks_publicip(app_id):
    """Check a real public TCP socket; exec/report errors propagate as failures."""
    if tcp_connected(app_id, TCP_CANARY, 443):
        raise vpn.VPNError('KILL_SWITCH_LEAK')


def live_failure_detail(exc):
    """Map structured errors to stable codes; sanitize only unstructured runtime text."""
    if isinstance(exc, (vpn.VPNError, apps.AppError)):
        code = str(exc)
        if apps.re.fullmatch(r'[A-Z0-9_]{1,64}', code):
            return code
    return safe_runtime_error(str(exc))


def main():
    region = os.environ.get('GSERVER_VPN_REGION', 'jp')
    if region not in vpn.REGIONS:
        raise SystemExit('GSERVER_VPN_REGION must be jp or kr')
    profile = PROFILE_ROOT / vpn.REGIONS[region]
    tunnel_cred = os.environ.get('GSERVER_CLOUDFLARED_CREDENTIAL')
    phase = 'PRECHECK'
    failure = None
    created = False
    project = None
    before = None
    storage_before = None
    print('========== GACE_RESULT_BEGIN ==========\nPROJECT=Gserver\nACTION=PC_VPN_CLOUDFLARE_LIVE_SMOKE', flush=True)
    with tempfile.TemporaryDirectory(prefix='gserver-vpn-live-') as workspace:
        bundle = Path(workspace) / 'bundle'
        try:
            if tunnel_cred:
                raise vpn.VPNError('CLOUDFLARE_REQUIRES_SEPARATE_AUTHORIZED_GATE')
            before = inventory()
            info = json.loads(docker('inspect', CORE))[0]
            if info['State'].get('Health', {}).get('Status') != 'healthy':
                raise vpn.VPNError('CORE_NOT_HEALTHY')
            storage_before = storage()
            app_image, vpn_image, tunnel_image = resolve_images()
            vpn.profile(profile, region)
            if region not in vpn.endpoint_pins():
                raise vpn.VPNError('ENDPOINT_PUBLIC_IPV4_PIN_REQUIRED')
            status = vpn.preflight(vpn_image, app_image, tunnel_image)
            validate_live_preflight(
                status,
                region,
                require_cloudflared=bool(tunnel_image and tunnel_cred),
            )
            phase = 'RENDER_BUNDLE'
            manifest = vpn.render(
                bundle,
                region,
                profile,
                vpn_image,
                app_image,
                cloudflared_image=None,
            )
            project = manifest['project']
            phase = 'START_BUNDLE'
            created = True
            with contextlib.redirect_stdout(io.StringIO()):
                vpn.start(bundle)
            app_id = service_container(project, 'app')
            verify_app_resolv_conf(app_id)
            print('APP_RESOLV_CONF_APPLIED=PASS', flush=True)
            print('APP_DNS_VPN_NAMESERVER=PASS', flush=True)
            phase = 'VPN_EGRESS'
            vpn_id = service_container(project, 'vpn')
            wg_before = wireguard_state(vpn_id)
            latencies = []
            exits = []
            for url in TRACE_URLS:
                start = time.monotonic()
                exits.append(https_exit(app_id, url, region))
                latencies.append(str(round(time.monotonic() - start, 3)))
            wg_after = wireguard_state(vpn_id)
            if exits[0] != exits[1]:
                raise vpn.VPNError('EGRESS_IP_CHANGED_DURING_PROBE')
            if wg_before[0] != wg_after[0] or any(wg_after[i] <= wg_before[i] for i in (1, 2)):
                raise vpn.VPNError('WIREGUARD_TRANSFER_NOT_OBSERVED')
            print('VPN_EXIT_IP_SHA256=' + hashlib.sha256(exits[0].encode('ascii')).hexdigest(), flush=True)
            print('VPN_HTTPS_LATENCY_SAMPLES_SEC=' + ','.join(latencies), flush=True)
            print('APP_HTTPS_LITERAL_AND_DNS=PASS', flush=True)
            print('VPN_EXIT_COUNTRY=' + region.upper(), flush=True)
            print('WIREGUARD_CONNECTION=PASS', flush=True)
            print('WAN_PACKETS=SENT_VIA_VPN_NAMESPACE', flush=True)
            phase = 'NET_GUARDS'
            verify_network_guards(app_id)
            print('DOCKER_EMBEDDED_DNS_UDP_TCP_BLOCKED=PASS', flush=True)
            print('IPV6_DISABLED_AND_PUBLIC_CONNECT_BLOCKED=PASS', flush=True)
            phase = 'KILL_SWITCH'
            if not tcp_connected(app_id, TCP_CANARY, 443):
                raise vpn.VPNError('KILL_SWITCH_POSITIVE_CONTROL_FAILED')
            guard_before = app_guard(app_id)
            docker('compose', '--project-name', project, '--project-directory', str(bundle),
                   '--env-file', '/dev/null', '-f', str(bundle / 'compose.json'),
                   'stop', '--timeout', '10', 'vpn')
            assert_vpn_stop_blocks_publicip(app_id)
            unchanged_guard(guard_before, app_guard(app_id))
            print('VPN_KILL_SWITCH_PUBLIC_TCP=PASS', flush=True)
            print('CLOUDFLARE=NOT_RUN_SEPARATE_AUTHORIZED_GATE', flush=True)
            print('PERFORMANCE=NOT_VERIFIED', flush=True)
        except (apps.AppError, vpn.VPNError, OSError, ValueError, KeyError, TypeError) as exc:
            failure = phase
            print('LIVE_FAILURE_CODE=' + live_failure_detail(exc), flush=True)
            if getattr(exc, 'diagnostic', ''):
                print('LIVE_COMMAND_ERROR=' + vpn.sanitize_diagnostic(exc.diagnostic, limit=1500), flush=True)
        finally:
            if created and project:
                try:
                    docker('compose', '--project-name', project, '--project-directory', str(bundle),
                           '--env-file', '/dev/null', '-f', str(bundle / 'compose.json'),
                           'down', '--timeout', '15', '--remove-orphans')
                except apps.AppError:
                    failure = failure or 'CLEANUP'
            if before is not None:
                try:
                    if inventory() != before:
                        raise vpn.VPNError('EXISTING_CONTAINER_CHANGED')
                    if storage_before is not None and storage() != storage_before:
                        raise vpn.VPNError('CORE_STORAGE_RESPONSE_CHANGED')
                    print('CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS', flush=True)
                except (apps.AppError, vpn.VPNError, ValueError, KeyError):
                    failure = failure or 'EXISTING_CONTAINER_READBACK'
    print('ACCEPTANCE_KERNEL_GUARD=NOT_THIS_SCRIPT')
    print('ACCEPTANCE_LIVE_VPN=' + ('FAIL' if failure else 'PASS'))
    print('ACCEPTANCE_CLOUDFLARE=NOT_RUN')
    print('VERIFY=' + ('FAIL' if failure else 'PASS'))
    print('ERROR=' + ('LIVE_' + failure if failure else 'NONE'))
    print('EXIT_CODE=' + ('1' if failure else '0'))
    print('PROJECT_END=Gserver\n========== GACE_RESULT_END ==========', flush=True)
    return 1 if failure else 0


if __name__ == '__main__':
    sys.exit(main())
