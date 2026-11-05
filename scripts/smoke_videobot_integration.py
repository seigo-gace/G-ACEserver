#!/usr/bin/env python3
"""Run the pinned VideoBot bootstrap against a disposable private Gserver Core.

No production credentials, Telegram, payment operations, image pull or deployment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import stat
import subprocess
import time

from local_docker import docker_command
from gserver_apps import AppError
from smoke_gserver_apps_host import CORE, inventory, storage

SOURCE_SHA = 'ae8a2385d52d0579468c2e5cb2f3307f94524666'
SOURCE_BLOBS = {
    'src/integrations/gserverEvents.mjs': '8301cfe5cad7b5c1b9c25e02a4c74bad3a2527d6',
    'src/runtime/config.mjs': '061cfaf0c5e09a1205e5de70ed7fb6a5f2bd58c6',
    'src/runtime/main.mjs': 'd6ba73d59558df2b52ce866d3c2ac0a9f2a9c380',
}
IMAGE = re.compile(r'(?:sha256:[a-f0-9]{64}|node@sha256:[a-f0-9]{64})\Z')
ID = re.compile(r'[a-f0-9]{64}\Z')

PROVISION = '''import os,pathlib,secrets,json
p=pathlib.Path('/var/lib/gserver')
for n in ('auth-token','bot-auth-token'):
 fd=os.open(p/n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'w') as f: f.write(secrets.token_hex(32))
print(json.dumps({'bot':(p/'bot-auth-token').read_text()}))
'''

# The real upstream main/config/adapter, not an imitation. Only a synthetic Bot
# credential reaches this client, through stdin and a container tmpfs file.
CLIENT = r'''
import { readFileSync, writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
const { token } = JSON.parse(readFileSync(0,'utf8'));
writeFileSync('/run/secrets/gserver_bot_token',token,{mode:0o600,flag:'wx'});
await import('/opt/videobot/src/runtime/main.mjs');
const {postGserverEvent} = await import('/opt/videobot/src/integrations/gserverEvents.mjs');
const baseUrl='http://gserver:8765/';
const event={bot:'create-videobot',event_id:'gserver-isolated-contract',event:'bot.request.completed',level:'info'};
for(let i=0;i<2;i++) {
 const result=await postGserverEvent({event,baseUrl,token});
 assert.deepEqual(result,{acceptedLocally:true,remoteDelivered:false});
}
const conflict=await postGserverEvent({event:{...event,outcome:'SKIP'},baseUrl,token});
assert.equal(conflict.acceptedLocally,false); assert.equal(conflict.status,409);
const denied=await postGserverEvent({event,baseUrl,token:'invalid-synthetic-token-00000000'});
assert.equal(denied.acceptedLocally,false); assert.equal(denied.status,401);
const ownerOnly=await fetch(new URL('/ready',baseUrl),{headers:{Authorization:'Bearer '+token},redirect:'error',signal:AbortSignal.timeout(3000)});
assert.equal(ownerOnly.status,401);
process.stdout.write('VIDEOBOT_BOOTSTRAP_ADMISSION_AUTH_REPLAY_CONFLICT=PASS\n');
'''


class ProbeError(Exception):
    pass


def source_directory(value):
    root = Path(value).expanduser().absolute()
    if root.resolve() != root or ',' in str(root) or not root.is_dir():
        raise ProbeError('SOURCE_DIRECTORY_UNSAFE')
    for name, expected in SOURCE_BLOBS.items():
        path = root / name
        if path.resolve() != path:
            raise ProbeError('SOURCE_SYMLINK')
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 100_000:
            raise ProbeError('SOURCE_FILE_UNSAFE')
        raw = path.read_bytes()
        digest = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if digest != expected:
            raise ProbeError('SOURCE_VERSION_MISMATCH')
    return root


def docker(*args, input=None):
    try:
        result = subprocess.run(docker_command() + list(args), input=input,
                                text=True, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise ProbeError('DOCKER_UNAVAILABLE') from None
    if result.returncode:
        # Never echo app diagnostics, provider bodies or credentials.
        raise ProbeError('DOCKER_OPERATION_FAILED_' + args[0].upper())
    return result.stdout.strip()


def bounded_container(network):
    return ['--pull', 'never', '--network', network, '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--pids-limit', '64', '--memory', '192m', '--cpus', '0.5',
            '--log-driver', 'local', '--log-opt', 'max-size=1m',
            '--log-opt', 'max-file=2', '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=16m',
            '--label', 'gserver.acceptance=videobot']


def container_id(value):
    if not ID.fullmatch(value):
        raise ProbeError('CONTAINER_ID_INVALID')
    return value


def wait_core(core):
    check = "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=2).status==200"
    for _ in range(30):
        try:
            docker('exec', core, 'python3', '-B', '-c', check)
            return
        except ProbeError:
            time.sleep(0.5)
    raise ProbeError('ISOLATED_CORE_NOT_READY')


def receipt(core):
    code = '''import sqlite3,hashlib,json
with sqlite3.connect('file:/var/lib/gserver/bot-spool/bot-events.sqlite3?mode=ro',uri=True) as c:
 c.execute('PRAGMA query_only=ON')
 assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 rows=c.execute('SELECT fingerprint,payload FROM events WHERE id=?',('gserver:create-videobot:gserver-isolated-contract',)).fetchall()
 assert len(rows)==1
 print(hashlib.sha256(json.dumps(rows).encode()).hexdigest())
'''
    digest = docker('exec', core, 'python3', '-B', '-c', code)
    if not ID.fullmatch(digest):
        raise ProbeError('SQLITE_RECEIPT_INVALID')
    return digest


def verify(source, node_image):
    source = source_directory(source)
    if not IMAGE.fullmatch(node_image):
        raise ProbeError('IMMUTABLE_LOCAL_NODE_IMAGE_REQUIRED')
    docker('image', 'inspect', node_image)
    existing = json.loads(docker('inspect', CORE))[0]
    if existing['State'].get('Health', {}).get('Status') != 'healthy':
        raise ProbeError('EXISTING_CORE_NOT_HEALTHY')
    core_image = existing['Image']
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', core_image):
        raise ProbeError('CORE_IMAGE_INVALID')
    before, storage_before = inventory(), storage()
    prefix = 'gserver-videobot-probe-' + secrets.token_hex(8)
    containers, volume, network = [], None, None
    try:
        if docker('volume', 'ls', '-q', '--filter', 'name=^' + prefix + '$'):
            raise ProbeError('RESOURCE_EXISTS')
        candidate = docker('volume', 'create', '--label', 'gserver.acceptance=' + prefix, prefix)
        info = json.loads(docker('volume', 'inspect', candidate))[0]
        if candidate != prefix or info.get('Labels', {}).get('gserver.acceptance') != prefix:
            raise ProbeError('VOLUME_NOT_OWNED')
        volume = candidate  # Select for cleanup only after ownership readback.
        network = docker('network', 'create', '--internal', '--label', 'gserver.acceptance=' + prefix, prefix)
        if not ID.fullmatch(network):
            network = None
            raise ProbeError('NETWORK_ID_INVALID')
        net = json.loads(docker('network', 'inspect', network))[0]
        if not net.get('Internal'):
            raise ProbeError('EXTERNAL_NETWORK_FORBIDDEN')
        core = container_id(docker('create', *bounded_container(network),
            '--network-alias', 'gserver', '--user', '65534:65534',
            '--mount', 'type=volume,source=' + volume + ',target=/var/lib/gserver',
            '-e', 'GSERVER_AUTH_FILE=/var/lib/gserver/auth-token',
            '-e', 'GSERVER_BOT_AUTH_FILE=/var/lib/gserver/bot-auth-token',
            '-e', 'GSERVER_BOT_SPOOL_DIR=/var/lib/gserver/bot-spool', core_image))
        containers.append(core)
        docker('start', core)
        wait_core(core)
        token = json.loads(docker('exec', core, 'python3', '-B', '-c', PROVISION))['bot']
        if not ID.fullmatch(token):
            raise ProbeError('SYNTHETIC_TOKEN_INVALID')

        def client():
            cid = container_id(docker('create', '-i', *bounded_container(network),
                '--user', '1000:1000', '--workdir', '/opt/videobot',
                '--mount', 'type=bind,source=' + str(source / 'src') + ',target=/opt/videobot/src,readonly',
                '--tmpfs', '/run/secrets:rw,noexec,nosuid,nodev,size=1m,uid=1000,gid=1000,mode=0700',
                '-e', 'NODE_ENV=production', '-e', 'GSERVER_BASE_URL=http://gserver:8765/',
                node_image, 'node', '--input-type=module', '-e', CLIENT))
            containers.append(cid)
            output = docker('start', '-a', '-i', cid, input=json.dumps({'token': token}))
            if 'VIDEOBOT_BOOTSTRAP_ADMISSION_AUTH_REPLAY_CONFLICT=PASS' not in output:
                raise ProbeError('CLIENT_RESULT_MISSING')

        client()
        digest = receipt(core)
        docker('restart', core)
        wait_core(core)
        client()
        if receipt(core) != digest:
            raise ProbeError('RESTART_RECEIPT_CHANGED')
        print('VIDEOBOT_BOOTSTRAP_PRIVATE_AUTH_REPLAY=PASS')
        print('VIDEOBOT_CORE_RESTART_SQLITE=PASS')
    finally:
        failed = False
        for cid in reversed(containers):
            try:
                docker('rm', '-f', cid)
            except ProbeError:
                failed = True
        for kind, resource in (('network', network), ('volume', volume)):
            if resource:
                try:
                    docker(kind, 'rm', resource)
                except ProbeError:
                    failed = True
        if failed:
            raise ProbeError('OWNED_CLEANUP_FAILED')
        if inventory() != before or storage() != storage_before:
            raise ProbeError('EXISTING_SERVICES_CHANGED')
        print('EXISTING_CORE_STORAGE_CONTAINERS_UNCHANGED=PASS')
    print('VIDEOBOT_SOURCE_SHA=' + SOURCE_SHA)
    print('TELEGRAM_SALES_RUNTIME=NOT_STARTED')
    print('GATEWAY_P015_DELIVERY=NOT_VERIFIED')
    print('VERIFY=PASS')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-source', required=True, help='Existing pinned app checkout or verified snapshot')
    parser.add_argument('--node-image', required=True, help='Immutable already-local Node image ID/digest')
    args = parser.parse_args()
    try:
        verify(args.app_source, args.node_image)
    except (ProbeError, AppError, OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR=' + (str(exc) if isinstance(exc, ProbeError) else type(exc).__name__))
        print('VIDEOBOT_ISOLATED_ACCEPTANCE=FAIL')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
