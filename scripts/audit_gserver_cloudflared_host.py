#!/usr/bin/env python3
"""Probe the already-local connector offline; no credential or provider operation."""
import json
import re
import secrets
import tempfile
from pathlib import Path

import gserver_apps as apps
import gserver_vpn as vpn
from smoke_gserver_apps_host import docker, inventory


def main():
    failure = None
    phase = "PRECHECK"
    before = None
    marker = secrets.token_hex(16)
    label = 'com.gace.gserver.cloudflared-audit=' + marker
    print('========== GACE_RESULT_BEGIN ==========\nPROJECT=Gserver\nACTION=CLOUDFLARED_LOCAL_IMAGE_AUDIT')
    try:
        before = inventory()
        hints = vpn.hints()
        image = hints.get('suggested_cloudflared_image', '')
        phase = 'IMAGE_METADATA'
        if image == 'LOCAL_PINNED_IMAGE_MISSING':
            raise vpn.VPNError('LOCAL_PINNED_IMAGE_MISSING')
        vpn.pinned(image)
        info = json.loads(docker('image', 'inspect', image))[0]['Config']
        entrypoint = info.get('Entrypoint')
        if entrypoint not in (['cloudflared'], ['/usr/local/bin/cloudflared']):
            raise vpn.VPNError('CLOUDFLARED_ENTRYPOINT_UNVERIFIED')
        base = ['run', '--rm', '--pull', 'never', '--network', 'none', '--read-only',
                '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--pids-limit', '32', '--memory', '128m', '--cpus', '0.5', '--log-driver', 'none',
                '--no-healthcheck', '--label', label, image]
        phase = 'NATIVE_VERSION'
        output = docker(*base, 'version')
        version = re.search(r'cloudflared version (\d{4}\.\d+\.\d+)', output)
        if not version or tuple(map(int, version[1].split('.'))) < (2025, 4, 0):
            raise vpn.VPNError('CLOUDFLARED_TOKEN_FILE_VERSION_REQUIRED')
        print('CLOUDFLARED_VERSION=' + version[1])
        phase = 'NATIVE_HELP'
        help_text = docker(*base, *vpn.TUNNEL_RUN_PREFIX, '--help')
        if '--token-file' not in help_text:
            raise vpn.VPNError('CLOUDFLARED_TOKEN_FILE_UNAVAILABLE')
        print('NATIVE_EXECUTION_UID65534=PASS\nNATIVE_TOKEN_FILE_SUPPORTED=PASS')
        phase = 'PRIVATE_STAGE_AND_UID_READ'
        app_image = vpn.pinned(hints.get('core_app_image', ''))
        with tempfile.TemporaryDirectory(prefix='gserver-cf-token-probe-', dir='/dev/shm') as temporary:
            directory = Path(temporary)
            vpn.stage_tunnel_credential(directory, b'gserver-offline-probe')
            source = directory / vpn.TUNNEL_RUNTIME_FILE
            code = ('import pathlib; assert pathlib.Path(' + repr(vpn.TUNNEL_CONTAINER_FILE) +
                    ').read_bytes()==b"gserver-offline-probe";print("TOKEN_FILE_READABLE")')
            config = {'services': {'probe': {'image': app_image, 'pull_policy': 'never',
                'entrypoint': ['python3', '-B', '-c', code], 'user': '65534:65534',
                'network_mode': 'none', 'read_only': True, 'cap_drop': ['ALL'],
                'security_opt': ['no-new-privileges:true'], 'healthcheck': {'disable': True},
                'pids_limit': 32, 'mem_limit': '128m', 'cpus': '0.5', 'restart': 'no',
                'logging': {'driver': 'none'}, 'labels': {label.split('=')[0]: marker},
                'secrets': [{'source': 'tunnel_token', 'target': 'gserver-tunnel-token'}]}},
                'secrets': {'tunnel_token': {'file': str(source)}}}
            compose_file = directory / 'compose.json'
            compose_file.write_text(json.dumps(config))
            compose_file.chmod(0o600)
            project = 'gace-cfprobe-' + marker[:16]
            compose = ['compose', '--project-name', project, '--env-file', '/dev/null',
                       '--project-directory', str(directory), '-f', str(compose_file)]
            if docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project).strip():
                raise vpn.VPNError('LOCAL_AUDIT_PROJECT_EXISTS_REFUSE_ADOPTION')
            try:
                output = docker(*compose, 'up', '--abort-on-container-exit', '--exit-code-from', 'probe',
                                '--no-build', '--pull', 'never')
                if 'TOKEN_FILE_READABLE' not in output:
                    raise vpn.VPNError('NONROOT_TOKEN_READ_UNVERIFIED')
            finally:
                docker(*compose, 'down', '--timeout', '10')
        print('SYNTHETIC_PRIVATE_TOKEN_STAGING_UID65534=PASS')
        print('NETWORK=NONE\nCREDENTIAL=NOT_USED\nPROVIDER_OPERATIONS=NONE')
    except (apps.AppError, vpn.VPNError, OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        failure = str(exc) if isinstance(exc, (apps.AppError, vpn.VPNError)) else 'LOCAL_AUDIT_REPORT_INVALID'
        if not re.fullmatch(r'[A-Z0-9_]{1,64}', failure):
            failure = 'LOCAL_AUDIT_FAILED'
    finally:
        if before is not None:
            try:
                # A timed-out client may leave a container; only this random label is owned.
                leftovers = docker('ps', '-aq', '--filter', 'label=' + label).split()
                if leftovers:
                    docker('rm', '-f', *leftovers)
                if inventory() != before:
                    raise vpn.VPNError('EXISTING_CONTAINER_CHANGED')
                print('EXISTING_CONTAINERS_UNCHANGED=PASS')
            except (apps.AppError, vpn.VPNError, OSError, ValueError, KeyError, TypeError):
                failure = failure or 'LOCAL_AUDIT_CLEANUP_OR_INVARIANT'
    if failure:
        print('LOCAL_FAILURE_PHASE=' + phase)
    print('ACCEPTANCE_CLOUDFLARE=NOT_RUN')
    print('VERIFY=' + ('FAIL' if failure else 'PASS'))
    print('ERROR=' + (failure or 'NONE'))
    print('EXIT_CODE=' + ('1' if failure else '0'))
    print('PROJECT_END=Gserver\n========== GACE_RESULT_END ==========')
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
