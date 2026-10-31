#!/usr/bin/env python3
"""Report credential slots and bundle readiness without live connections or secret output."""
import argparse
import json
import os
from pathlib import Path
import sys

import gserver_vpn as vpn


SLOTS = (
    ('wireguard_profile_jp', 'owner-only Windscribe JP profile path', 'gserver_vpn.py verify jp PROFILE'),
    ('wireguard_profile_kr', 'owner-only Windscribe KR profile path', 'gserver_vpn.py verify kr PROFILE'),
    ('endpoint_pin_jp', 'private endpoint-cache jp IPv4 pin', 'endpoint-cache.json jp key'),
    ('endpoint_pin_kr', 'private endpoint-cache kr IPv4 pin', 'endpoint-cache.json kr key'),
    ('vpn_image_digest', 'pinned local Gluetun image', 'gserver_vpn.py preflight --vpn-image IMAGE'),
    ('app_image_digest', 'pinned local app image', 'preflight --app-image IMAGE'),
    ('cloudflared_image_digest', 'pinned local cloudflared image', 'preflight --cloudflared-image IMAGE'),
    ('cloudflared_tunnel_credential', '0600 original; UID65534 0400 private native token-file staging', 'bundle/cloudflared.credential at start'),
    ('bot_app_compose', 'Bot-owned Compose (separate repo)', 'gserver_apps.py verify APP COMPOSE'),
    ('bot_webhook_secret', 'Telegram webhook secret (Bot owner)', 'WAIT_REAL_CONNECTION'),
    ('gateway_url_token', 'existing Gateway private HTTPS (optional bridge)', 'WAIT_REAL_CONNECTION'),
    ('vault_formal_contract', 'Libral Vault when approved', 'WAIT_REAL_CONNECTION'),
)


def bundle_state(directory):
    directory, manifest = vpn.load(directory)
    compose = json.loads((directory / 'compose.json').read_text())
    services = set(compose.get('services', {}))
    credential = (directory / vpn.TUNNEL_CREDENTIAL).is_file()
    return {
        'bundle': 'VALID',
        'project': manifest['project'],
        'components': sorted(services),
        'cloudflared_credential_file': 'PRESENT' if credential else 'MISSING',
        'live_connection': 'WAIT_REAL_CONNECTION',
    }


def local_slot_status():
    profile_root = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'gserver/vpn-profiles'
    pins = vpn.endpoint_pins()
    out = {}
    for region, name in vpn.REGIONS.items():
        path = profile_root / name
        out['wireguard_profile_' + region] = 'PRESENT' if path.is_file() and path.stat().st_mode & 0o077 == 0 else 'MISSING'
        out['endpoint_pin_' + region] = 'CONFIGURED' if region in pins else 'NOT_CONFIGURED'
    hints = vpn.hints()
    out['docker_access'] = hints.get('docker_access', 'UNKNOWN')
    out['vpn_image'] = hints.get('suggested_gluetun_image', 'UNKNOWN')
    out['cloudflared_image'] = hints.get('suggested_cloudflared_image', 'UNKNOWN')
    out['core_app_image'] = hints.get('core_app_image', 'UNKNOWN')
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', help='Private VPN bundle directory to validate offline')
    parser.add_argument('--local-status', action='store_true', help='Summarize owner-local credential slots without secrets')
    args = parser.parse_args()
    print('========== GACE_RESULT_BEGIN ==========')
    print('PROJECT=Gserver')
    print('ACTION=CONNECTION_READINESS_REPORT')
    for slot, purpose, verify in SLOTS:
        print(f'SLOT={slot};PURPOSE={purpose};VERIFY={verify}')
    if args.local_status:
        for key, value in sorted(local_slot_status().items()):
            print(f'LOCAL_{key.upper()}={value}')
    if args.bundle:
        try:
            state = bundle_state(args.bundle)
            for key, value in state.items():
                print(f'BUNDLE_{key.upper()}={value}')
            ready = 'cloudflared' not in state['components'] or state['cloudflared_credential_file'] == 'PRESENT'
            print('READY_FOR_CREDENTIALS=' + ('PARTIAL_BUNDLE_OK' if ready else 'TUNNEL_CREDENTIAL_MISSING'))
        except vpn.VPNError as exc:
            print('BUNDLE_STATE=INVALID')
            print('BUNDLE_ERROR=' + str(exc))
            print('READY_FOR_CREDENTIALS=NO')
    else:
        print('READY_FOR_CREDENTIALS=REPORT_ONLY')
    print('BOT_BRIDGE=/bot/events is Gserver ops logging; Bot send/receive E2E is separate app owner scope')
    print('EXIT_CODE=0')
    print('PROJECT_END=Gserver')
    print('========== GACE_RESULT_END ==========')
    return 0


if __name__ == '__main__':
    sys.exit(main())
