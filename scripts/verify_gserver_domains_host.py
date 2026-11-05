#!/usr/bin/env python3
"""Offline native cloudflared routing audit with fictional domains; no live writes."""
import argparse
import json
from pathlib import Path
import re
import tempfile

import gserver_domains as domains
from gserver_apps import AppError
from smoke_gserver_apps_host import docker, inventory

ROOT = Path(__file__).resolve().parents[1]


def native(image, config, *args):
    # The caller provides a synthetic config, never a credential-bearing file.
    cid = docker('create', '--pull', 'never', '--network', 'none', '--read-only',
        '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
        '--pids-limit', '32', '--memory', '128m', '--cpus', '0.5', '--log-driver', 'none',
        '-e', 'GOMAXPROCS=2', '--mount', 'type=bind,source=' + str(config) + ',target=/etc/cloudflared/config.json,readonly',
        image, 'tunnel', '--config', '/etc/cloudflared/config.json', 'ingress', *args).strip()
    if not re.fullmatch(r'[a-f0-9]{64}', cid):
        raise domains.DomainError('INVALID_OWNED_CONTAINER_ID')
    try:
        output = docker('start', '-a', cid)
        code = docker('inspect', '--format', '{{.State.ExitCode}}', cid).strip()
        domains.require(code == '0', 'NATIVE_INGRESS_CHECK_FAILED')
        return output
    finally:
        docker('rm', '-f', cid)


def verify(image):
    domains.require(re.fullmatch(r'sha256:[a-f0-9]{64}', image), 'IMMUTABLE_LOCAL_IMAGE_REQUIRED')
    docker('image', 'inspect', image)
    before = inventory()
    try:
        policy = json.loads((ROOT / 'deploy/domain-policy.example.json').read_text())
        routes = json.loads((ROOT / 'deploy/domain-bindings.example.json').read_text())['bindings']
        with tempfile.TemporaryDirectory(prefix='gserver-domain-audit-') as temporary:
            root = Path(temporary)
            store = domains.Store(root / 'state')
            first = store.prepare(policy, routes, None)
            second = store.switch(policy, 'videobot', 'webhook', 'video.example.net', first)
            store.export(policy, second, root / 'after')
            files = sorted((root / 'after').glob('*.ingress.json'))
            for path in files:
                # Only these fictional, generated files become readable by UID65534.
                path.chmod(0o644)
                native(image, path, 'validate')
            video = root / 'after/00000000-0000-0000-0000-000000000001.ingress.json'
            for host in ('video.example.net', 'video.example.com'):
                result = native(image, video, 'rule', 'https://' + host + '/telegram/webhook')
                domains.require('http://127.0.0.1:8080' in result, 'HOST_NOT_ROUTED_TO_APP')
            result = native(image, video, 'rule', 'https://unknown.example.net/')
            domains.require('http_status:404' in result, 'UNKNOWN_HOST_NOT_DENIED')
            third = store.rollback(policy, first, second)
            domains.require(store.load(third)['bindings'] == store.load(first)['bindings'], 'ROLLBACK_MISMATCH')
            store.export(policy, third, root / 'rollback')
            original = root / 'rollback/00000000-0000-0000-0000-000000000001.ingress.json'
            original.chmod(0o644)
            native(image, original, 'validate')
        print('DOMAIN_MULTI_PROJECT_NATIVE_INGRESS=PASS')
        print('DOMAIN_NEW_AND_OLD_HOST_ROUTE=PASS')
        print('DOMAIN_UNKNOWN_HOST_DENIED=PASS')
        print('DOMAIN_DESIRED_ROLLBACK=PASS')
    finally:
        domains.require(inventory() == before, 'EXISTING_CONTAINERS_CHANGED')
    print('EXISTING_CONTAINERS_UNCHANGED=PASS')
    print('NETWORK=NONE\nPROVIDER_OPERATIONS=NONE\nDOMAIN_LIVE_STATUS=NOT_VERIFIED\nVERIFY=PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cloudflared-image', required=True, help='Existing local sha256 image ID')
    args = parser.parse_args()
    try:
        verify(args.cloudflared_image)
    except (domains.DomainError, AppError, OSError, ValueError, TypeError, KeyError):
        print('DOMAIN_OFFLINE_AUDIT=FAIL')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
