#!/usr/bin/env python3
"""Kernel-only namespace guard test. Private bridge peer canary, no WAN/VPN/WireGuard keys."""
import contextlib
import io
import ipaddress
import json
from pathlib import Path
import secrets
import sys
import tempfile

import gserver_apps as apps
import gserver_vpn as vpn
from smoke_gserver_apps_host import docker, inventory, storage, CORE, safe_runtime_error

PORT = 19763
CANARY_PORT = 19764


def counters(report):
    return sum(int(expr['counter'].get('packets', 0))
               for value in report['nft'].get('nftables', [])
               for expr in value.get('rule', {}).get('expr', []) if 'counter' in expr)


def service_container(project, service):
    ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project,
                 '--filter', 'label=com.docker.compose.service=' + service).split()
    if len(ids) != 1:
        raise vpn.VPNError('SERVICE_CONTAINER_MISSING')
    return ids[0]


def private_peer_ip(container_id):
    info = json.loads(docker('inspect', container_id))[0]
    networks = info['NetworkSettings']['Networks']
    if len(networks) != 1:
        raise vpn.VPNError('PROBE_NETWORK_INVALID')
    address = ipaddress.ip_address(next(iter(networks.values()))['IPAddress'])
    if (address.version != 4 or not address.is_private or address.is_loopback
            or address.is_link_local or address.is_unspecified):
        raise vpn.VPNError('NONPRIVATE_CANARY_FORBIDDEN')
    return str(address)


def connect(container, address, port, allowed):
    # The only non-loopback destination is another container on the same private
    # bridge network; no public IP/domain, credentials or request body is sent.
    code = ("import socket,sys\ns=socket.socket();s.settimeout(3)\n"
            "try:\n s.connect((" + repr(address) + "," + str(port) + ")); ok=True\n"
            "except OSError:\n ok=False\n"
            "finally:\n s.close()\n"
            "sys.exit(0 if ok==" + repr(allowed) + " else 1)\n")
    try:
        docker('exec', container, 'python3', '-c', code)
    except apps.AppError as exc:
        raise vpn.VPNError('CANARY_CONNECT_FAILED', diagnostic=exc.diagnostic) from exc


def probe_spec(image, port):
    server = ("import socket\ns=socket.socket();s.bind(('127.0.0.1'," + str(port) + "));s.listen(4)\n"
              "while True:\n c,a=s.accept();c.close()\n")
    return {'image': image, 'restart': 'no', 'read_only': True,
            'user': '65534:65534', 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'pids_limit': 32, 'mem_limit': '64m', 'cpus': '0.25',
            'logging': {'driver': 'local', 'options': {'max-size': '1m', 'max-file': '2'}},
            'command': ['python3', '-B', '-u', '-c', server],
            'healthcheck': {'test': ['CMD', 'python3', '-c',
                "import socket; s=socket.create_connection(('127.0.0.1'," + str(port) + "),1);s.close()"],
                'interval': '1s', 'timeout': '2s', 'retries': 10}}


def canary_spec(image, port):
    server = ("import socket\ns=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
              "s.bind(('0.0.0.0'," + str(port) + "));s.listen(4)\n"
              "while True:\n c,a=s.accept();c.close()\n")
    return {'image': image, 'restart': 'no', 'read_only': True,
            'user': '65534:65534', 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'pids_limit': 32, 'mem_limit': '64m', 'cpus': '0.25',
            'logging': {'driver': 'local', 'options': {'max-size': '1m', 'max-file': '2'}},
            'command': ['python3', '-B', '-u', '-c', server],
            'healthcheck': {'test': ['CMD', 'python3', '-c',
                "import socket; s=socket.create_connection(('127.0.0.1'," + str(port) + "),1);s.close()"],
                'interval': '1s', 'timeout': '2s', 'retries': 10}}


def main():
    phase = 'PRECHECK'
    created = False
    before = None
    storage_before = None
    failure = None
    print('========== GACE_RESULT_BEGIN ==========\nPROJECT=Gserver\nACTION=PC_NAMESPACE_GUARD_KERNEL_SMOKE', flush=True)
    with tempfile.TemporaryDirectory(prefix='gserver-guard-smoke-') as directory:
        file = Path(directory) / 'compose.json'
        rules = Path(directory) / 'guard.nft'
        name = 'netprobe-' + secrets.token_hex(8)
        project = apps.project(name)
        try:
            before = inventory()
            info = json.loads(docker('inspect', CORE))[0]
            if info['State'].get('Health', {}).get('Status') != 'healthy':
                raise vpn.VPNError('CORE_NOT_HEALTHY')
            storage_before = storage()
            image = info['Image']
            vpn.pinned(image)
            phase = 'PROJECT_GUARD'
            if docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project).strip():
                raise vpn.VPNError('PROJECT_EXISTS')
            if project + '_default' in docker('network', 'ls', '--format', '{{.Name}}').splitlines():
                raise vpn.VPNError('NETWORK_EXISTS')
            config = {'services': {'canary': canary_spec(image, CANARY_PORT),
                                   'probe': {**probe_spec(image, PORT), 'depends_on': ['canary']}}}
            file.write_text(json.dumps(config))
            rules.write_text(vpn.guard_rules('93.184.216.34', 51820))
            phase = 'START_LOCAL_PROBE'
            created = True
            with contextlib.redirect_stdout(io.StringIO()):
                apps.execute('start', file, name)
            probe = service_container(project, 'probe')
            canary = service_container(project, 'canary')
            probe_info = json.loads(docker('inspect', probe))[0]
            if probe_info['Config']['Labels']['com.docker.compose.project'] != project:
                raise vpn.VPNError('PROBE_OWNER_MISMATCH')
            canary_ip = private_peer_ip(canary)
            phase = 'CANARY_BASELINE'
            connect(probe, canary_ip, CANARY_PORT, True)
            print('PRIVATE_CANARY_BASELINE=PASS', flush=True)
            pid = probe_info['State']['Pid']
            phase = 'INSTALL_GUARD'
            initial = vpn.namespace_guard(pid, rules)
            after = json.loads(docker('inspect', probe))[0]
            current = vpn.namespace_guard(pid)
            if after['State']['Pid'] != pid or current['inode'] != initial['inode']:
                raise vpn.VPNError('PROBE_NAMESPACE_CHANGED')
            phase = 'LOOPBACK_POSITIVE'
            connect(probe, '127.0.0.1', PORT, True)
            print('LOOPBACK_ALLOWED=PASS', flush=True)
            phase = 'CANARY_DENY'
            count = counters(current)
            connect(probe, canary_ip, CANARY_PORT, False)
            final = vpn.namespace_guard(pid)
            if counters(final) <= count or vpn.policy_fingerprint(final) != vpn.policy_fingerprint(initial):
                raise vpn.VPNError('DENY_COUNTER_OR_POLICY_MISMATCH')
            print('PRIVATE_CANARY_BLOCKED=PASS\nDROP_COUNTER_INCREASED=PASS', flush=True)
        except (apps.AppError, vpn.VPNError, OSError, ValueError, KeyError, TypeError) as exc:
            failure = phase
            if isinstance(exc, (apps.AppError, vpn.VPNError)):
                print('GUARD_FAILURE_DETAIL=' + safe_runtime_error(str(exc)), flush=True)
                if getattr(exc, 'diagnostic', ''):
                    print('GUARD_COMMAND_ERROR=' + safe_runtime_error(exc.diagnostic), flush=True)
        finally:
            if created:
                try:
                    apps.run(apps.command(file, name) + ['down', '--timeout', '10'])
                except apps.AppError:
                    failure = 'CLEANUP'
            if before is not None:
                try:
                    if inventory() != before:
                        raise vpn.VPNError('EXISTING_CONTAINER_CHANGED')
                    if storage_before is not None and storage() != storage_before:
                        raise vpn.VPNError('CORE_STORAGE_RESPONSE_CHANGED')
                    print('CORE_STORAGE_OTHER_CONTAINERS_UNCHANGED=PASS', flush=True)
                except (apps.AppError, vpn.VPNError, ValueError, KeyError):
                    failure = 'EXISTING_CONTAINER_READBACK'
    print('WIREGUARD_CONNECTION=NOT_TESTED\nWAN_PACKETS=NOT_SENT\nCLOUDFLARE=NOT_CHANGED')
    print('VERIFY=' + ('FAIL' if failure else 'PASS'))
    print('ERROR=' + ('NAMESPACE_GUARD_' + failure if failure else 'NONE'))
    print('EXIT_CODE=' + ('1' if failure else '0'))
    print('PROJECT_END=Gserver\n========== GACE_RESULT_END ==========', flush=True)
    return 1 if failure else 0


if __name__ == '__main__':
    sys.exit(main())
