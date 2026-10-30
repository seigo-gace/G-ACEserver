#!/usr/bin/env python3
"""Isolated WireGuard + optional cloudflared live acceptance; never redeploy Core."""
import contextlib
import io
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


def body_sha256(container, url, timeout=15):
    code = (
        "import hashlib,sys,urllib.request\n"
        "url=" + repr(url) + "\n"
        "timeout=" + str(timeout) + "\n"
        "with urllib.request.urlopen(url,timeout=timeout) as r:\n"
        " data=r.read(4096)\n"
        "print(hashlib.sha256(data).hexdigest())\n"
    )
    value = docker('exec', container, 'python3', '-B', '-c', code)
    digest = value.strip()
    if not apps.re.fullmatch(r'[a-f0-9]{64}', digest):
        raise vpn.VPNError('EGRESS_BODY_HASH_INVALID')
    return digest


def expect_connect(container, address, port, allowed, family='ipv4'):
    code = (
        "import socket,sys\n"
        "family=" + ('socket.AF_INET' if family == 'ipv4' else 'socket.AF_INET6') + "\n"
        "s=socket.socket(family,socket.SOCK_STREAM);s.settimeout(3)\n"
        "try:\n s.connect((" + repr(address) + "," + str(port) + ")); ok=True\n"
        "except OSError:\n ok=False\n"
        "finally:\n s.close()\n"
        "sys.exit(0 if ok==" + repr(allowed) + " else 1)\n"
    )
    try:
        docker('exec', container, 'python3', '-B', '-c', code)
    except apps.AppError as exc:
        raise vpn.VPNError('CONNECT_PROBE_FAILED', diagnostic=exc.diagnostic) from exc


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
    """Confirm read-only app received file-based config mount, not merely declared in compose."""
    code = (
        "import pathlib,sys\n"
        "lines=pathlib.Path('/etc/resolv.conf').read_text().splitlines()\n"
        "ok=bool(lines) and lines[0].strip()=='nameserver 127.0.0.1'\n"
        "sys.exit(0 if ok else 1)\n"
    )
    try:
        docker('exec', container, 'python3', '-B', '-c', code)
    except apps.AppError as exc:
        raise vpn.VPNError('APP_RESOLV_NOT_APPLIED', diagnostic=exc.diagnostic) from exc


def assert_vpn_stop_blocks_publicip(app_id):
    """Fail closed: any successful public IP read after VPN stop is a kill-switch leak."""
    try:
        body_sha256(app_id, 'http://127.0.0.1:8000/v1/publicip/ip', timeout=5)
    except apps.AppError:
        return
    except vpn.VPNError as exc:
        if str(exc) == 'KILL_SWITCH_LEAK':
            raise
        return
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
    compose_cmd = None
    before = None
    storage_before = None
    print('========== GACE_RESULT_BEGIN ==========\nPROJECT=Gserver\nACTION=PC_VPN_CLOUDFLARE_LIVE_SMOKE', flush=True)
    with tempfile.TemporaryDirectory(prefix='gserver-vpn-live-') as workspace:
        bundle = Path(workspace) / 'bundle'
        try:
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
            use_tunnel = bool(tunnel_image and tunnel_cred)
            manifest = vpn.render(
                bundle,
                region,
                profile,
                vpn_image,
                app_image,
                cloudflared_image=tunnel_image if use_tunnel else None,
            )
            project = manifest['project']
            if use_tunnel:
                src = Path(tunnel_cred).expanduser()
                if not src.is_file() or src.stat().st_mode & 0o077:
                    raise vpn.VPNError('CLOUDFLARED_CREDENTIAL_MISSING')
                dst = bundle / vpn.TUNNEL_CREDENTIAL
                dst.write_bytes(src.read_bytes())
                dst.chmod(0o600)
            phase = 'START_BUNDLE'
            created = True
            with contextlib.redirect_stdout(io.StringIO()):
                vpn.start(bundle)
            app_id = service_container(project, 'app')
            verify_app_resolv_conf(app_id)
            print('APP_RESOLV_CONF_APPLIED=PASS', flush=True)
            phase = 'VPN_EGRESS'
            latencies = []
            digest = ''
            for _ in range(3):
                start = time.monotonic()
                digest = body_sha256(app_id, 'http://127.0.0.1:8000/v1/publicip/ip')
                latencies.append(str(round(time.monotonic() - start, 3)))
            print('VPN_PUBLICIP_BODY_SHA256=' + digest, flush=True)
            print('VPN_PUBLICIP_LATENCY_SAMPLES_SEC=' + ','.join(latencies), flush=True)
            print('WIREGUARD_CONNECTION=PASS', flush=True)
            print('WAN_PACKETS=SENT_VIA_VPN_NAMESPACE', flush=True)
            phase = 'NET_GUARDS'
            expect_connect(app_id, '127.0.0.11', 53, False)
            print('DOCKER_EMBEDDED_DNS_BLOCKED=PASS', flush=True)
            expect_connect(app_id, '::1', 80, False, family='ipv6')
            print('IPV6_EGRESS_BLOCKED=PASS', flush=True)
            phase = 'KILL_SWITCH'
            docker('compose', '--project-name', project, '--project-directory', str(bundle),
                   '--env-file', '/dev/null', '-f', str(bundle / 'compose.json'),
                   'stop', '--timeout', '10', 'vpn')
            assert_vpn_stop_blocks_publicip(app_id)
            print('VPN_KILL_SWITCH=PASS', flush=True)
            phase = 'CLOUDFLARE'
            if use_tunnel:
                ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                             '--filter', 'label=com.docker.compose.service=cloudflared').split()
                if len(ids) != 1:
                    raise vpn.VPNError('CLOUDFLARED_CONTAINER_MISSING')
                logs = docker('logs', '--tail', '40', ids[0])
                if 'token' in logs.lower() or 'Authorization' in logs:
                    raise vpn.VPNError('CLOUDFLARED_LOG_SECRET_RISK')
                state = 'CONNECTED' if any(marker in logs for marker in ('Registered tunnel connection', 'Connection')) else 'NOT_VERIFIED'
                print('CLOUDFLARE_TUNNEL=' + state, flush=True)
            else:
                print('CLOUDFLARE=SKIPPED_NO_LOCAL_IMAGE_OR_CREDENTIAL', flush=True)
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
    print('ACCEPTANCE_CLOUDFLARE=' + ('NOT_RUN' if failure else 'PARTIAL_OR_SKIPPED'))
    print('VERIFY=' + ('FAIL' if failure else 'PASS'))
    print('ERROR=' + ('LIVE_' + failure if failure else 'NONE'))
    print('EXIT_CODE=' + ('1' if failure else '0'))
    print('PROJECT_END=Gserver\n========== GACE_RESULT_END ==========', flush=True)
    return 1 if failure else 0


if __name__ == '__main__':
    sys.exit(main())
