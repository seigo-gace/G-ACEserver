#!/usr/bin/env python3
"""Read-only post-power-loss checks; no stop/start, spool claim, repair or secrets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

from gserver_apps import AppError, run, DOCKER_SOCKET

# This program runs inside the existing Core. Token/SQLite rows never leave it.
CORE_CHECK = '''import os,json,pathlib,sqlite3,urllib.request
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
key=pathlib.Path(os.environ['GSERVER_AUTH_FILE']).read_text().strip()
for route in ('ready','files'):
 req=urllib.request.Request('http://127.0.0.1:8765/'+route,headers={'Authorization':'Bearer '+key})
 with opener.open(req,timeout=5) as r:
  assert r.status==200
p=pathlib.Path(os.environ['GSERVER_BOT_SPOOL_DIR'])/'bot-events.sqlite3'
assert p.is_file() and not p.is_symlink()
with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=4) as c:
 c.execute('PRAGMA query_only=ON')
 assert c.execute('PRAGMA quick_check').fetchall()==[('ok',)]
 count=c.execute('SELECT count(*) FROM events').fetchone()[0]
print(json.dumps({'owner_storage':'PASS','sqlite_quick_check':'PASS','spool_rows':count}))
'''


def main():
    result = {'scope': 'post_power_loss_current_read_only',
              'automatic_windows_to_wsl_start': 'NOT_VERIFIED',
              'pre_post_data_comparison': 'NOT_AVAILABLE',
              'complete_restore_acceptance': 'NOT_COMPLETE'}
    try:
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with client.open('http://127.0.0.1:18765/health', timeout=4) as response:
            if response.status != 200:
                raise ValueError()
        result['core_http'] = 'PASS'
        docker = ([] if os.geteuid() == 0 else ['sudo', '-n']) + ['docker', '--host', DOCKER_SOCKET]
        info = json.loads(run(docker + ['inspect', 'gace-gserver-gserver-1']))[0]
        if info['State'].get('Health', {}).get('Status') != 'healthy':
            raise ValueError()
        result['container_healthy'] = 'PASS'
        value = json.loads(run(docker + ['exec', 'gace-gserver-gserver-1', 'python3', '-c', CORE_CHECK]))
        if value.get('owner_storage') != 'PASS' or value.get('sqlite_quick_check') != 'PASS' or not isinstance(value.get('spool_rows'), int):
            raise ValueError()
        result.update(value)
        result['current_recovery_checks'] = 'PASS'
    except (AppError, OSError, ValueError, KeyError, TypeError):
        result['current_recovery_checks'] = 'NOT_VERIFIED'
        print(json.dumps(result))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
