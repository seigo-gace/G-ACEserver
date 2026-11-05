"""Use existing Windows tunnel identity for one protected, read-only native list."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

import gserver_vpn as vpn
from smoke_gserver_apps_host import docker
from gserver_apps import AppError

WINDOWS_METADATA = r'''
$ErrorActionPreference='Stop'
try {
 $directory=Join-Path $env:USERPROFILE '.cloudflared'
 $certificate=Join-Path $directory 'cert.pem'
 $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
 $allowed=@($sid,'S-1-5-18','S-1-5-32-544')
 $acl=Get-Acl -LiteralPath $certificate
 $owner=$acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
 $unsafe=@($acl.Access | Where-Object {
  $_.AccessControlType -eq 'Allow' -and
  ($_.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::ReadData) -and
  $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -notin $allowed
 })
 $linked=((Get-Item -LiteralPath $certificate).Attributes -band [IO.FileAttributes]::ReparsePoint) -or
         ((Get-Item -LiteralPath $directory).Attributes -band [IO.FileAttributes]::ReparsePoint)
 [pscustomobject]@{Directory=$directory;Protected=($owner -in $allowed -and $unsafe.Count -eq 0 -and -not $linked);Sha256=$(if($owner -in $allowed -and $unsafe.Count -eq 0 -and -not $linked){(Get-FileHash -LiteralPath $certificate -Algorithm SHA256).Hash}else{''})} | ConvertTo-Json -Compress
} catch { Write-Output '{}' }
'''


def windows_identity():
    """Windows ACL is authoritative for DrvFS; never relax original permissions."""
    command = ['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
               '-NoProfile', '-NonInteractive', '-EncodedCommand',
               base64.b64encode(WINDOWS_METADATA.encode('utf-16le')).decode('ascii')]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
        data = json.loads(result.stdout.strip())
        if data.get('Protected') is not True:
            raise vpn.VPNError('WINDOWS_ORIGIN_CERT_ACL_UNVERIFIED')
        converted = subprocess.run(['wslpath', '-u', data['Directory']], capture_output=True,
                                   text=True, timeout=10, check=True)
        root = Path(converted.stdout.strip())
        if not root.is_absolute() or root.name != '.cloudflared' or root.is_symlink():
            raise ValueError()
        path = root / 'cert.pem'
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError()
        certificate = path.read_bytes()
        if hashlib.sha256(certificate).hexdigest() != data['Sha256'].lower():
            raise vpn.VPNError('WINDOWS_ORIGIN_CERT_CHANGED')
        return parse_identity(root, certificate)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        raise vpn.VPNError('WINDOWS_ORIGIN_CERT_METADATA_UNAVAILABLE') from exc


def parse_identity(root, certificate):
    try:
        block = re.fullmatch(rb'-----BEGIN ARGO TUNNEL TOKEN-----\s+([A-Za-z0-9+/=\s]+)-----END ARGO TUNNEL TOKEN-----', certificate.strip())
        if not block:
            raise ValueError()
        fields = json.loads(base64.b64decode(re.sub(rb'\s', b'', block[1]), validate=True))
        if not all(isinstance(fields.get(k), str) and fields[k] for k in ('accountID', 'zoneID', 'apiToken')):
            raise ValueError()
        paths = list(root.glob('*.json'))
        if len(paths) > 32:
            raise ValueError()
        targets = []
        for path in paths:
            if path.is_symlink() or path.stat().st_size > 65536:
                raise ValueError()
            credential = json.loads(path.read_bytes())
            if not isinstance(credential, dict) or not {'TunnelID', 'AccountTag', 'TunnelSecret'} <= credential.keys():
                continue
            identity = str(uuid.UUID(credential['TunnelID']))
            if identity != path.stem.lower() or credential['AccountTag'] != fields['accountID']:
                continue
            targets.append(identity)
        if not targets:
            raise vpn.VPNError('MATCHING_LOCAL_TUNNEL_CREDENTIAL_MISSING')
        return {'certificate': certificate, 'certificate_sha256': hashlib.sha256(certificate).hexdigest(),
                'account_id': fields['accountID'], 'zone_id': fields['zoneID'], 'targets': targets}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise vpn.VPNError('WINDOWS_TUNNEL_IDENTITY_INVALID') from exc


def discover(bundle, vpn_container, project, image, *, identity):
    """No tunnel run/route/delete verb, generic Account API or broker replacement."""
    vpn.pinned(image)
    vpn.stage_tunnel_credential(bundle, identity['certificate'], kind='origin-cert')
    mounts = ['type=bind,src=' + str(bundle / vpn.ORIGIN_RUNTIME_FILE) + ',dst=' + vpn.ORIGIN_CONTAINER_FILE + ',readonly',
              'type=bind,src=' + str(bundle / vpn.APP_RESOLV_FILE) + ',dst=/etc/resolv.conf,readonly']
    command = ['run', '--rm', '--pull', 'never', '--network', 'container:' + vpn_container,
               '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
               '--read-only', '--no-healthcheck', '--pids-limit', '64', '--memory', '256m', '--cpus', '1.0',
               '--log-driver', 'none', '--label', 'com.docker.compose.project=' + project,
               '--label', 'com.docker.compose.service=cf-discovery']
    for mount in mounts:
        command += ['--mount', mount]
    rows = []
    for target in identity['targets']:
        # Filter on the provider, not only after retrieving unrelated resources.
        request = command + [image, 'tunnel', '--origincert', vpn.ORIGIN_CONTAINER_FILE,
                             'list', '--output', 'json', '--id', target]
        try:
            output = docker(*request)
        except AppError:
            # Native diagnostics may contain private provider metadata.
            raise vpn.VPNError('CLOUDFLARE_DISCOVERY_COMMAND_FAILED') from None
        if len(output) > 2 * 1024 * 1024:
            raise vpn.VPNError('CLOUDFLARE_DISCOVERY_RESPONSE_TOO_LARGE')
        try:
            response = json.loads(output)
            if not isinstance(response, list) or len(response) != 1 or response[0].get('id') != target:
                raise ValueError()
            rows.extend(response)
        except (ValueError, TypeError, KeyError, AttributeError):
            raise vpn.VPNError('CLOUDFLARE_DISCOVERY_RESPONSE_INVALID') from None
    try:
        selected = []
        for row in rows:
            if row.get('id') not in identity['targets']:
                continue
            name = row.get('name')
            if not isinstance(name, str) or len(name) > 256 or not isinstance(row.get('connections', []), list):
                raise ValueError()
            selected.append({'id': row['id'], 'name': name,
                             'connections': len(row.get('connections', [])), 'deleted': bool(row.get('deleted_at'))})
        if not selected:
            raise vpn.VPNError('LOCAL_TUNNEL_NOT_FOUND_IN_PROVIDER')
        return {'scope': 'read_only_native_tunnel_list', 'account_id': identity['account_id'],
                'zone_id': identity['zone_id'], 'certificate_sha256': identity['certificate_sha256'],
                'tunnels': selected, 'domain_owner': 'NOT_VERIFIED', 'provider_mutations': 'NONE'}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise vpn.VPNError('CLOUDFLARE_DISCOVERY_RESPONSE_INVALID') from exc


def save_receipt(value):
    """Metadata only, after all VPN/cleanup invariants succeed; never the cert/token."""
    directory = Path.home() / '.local/state/gserver/verification'
    if directory.resolve() != directory:
        raise vpn.VPNError('DISCOVERY_RECEIPT_DIRECTORY_UNSAFE')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077:
        raise vpn.VPNError('DISCOVERY_RECEIPT_DIRECTORY_UNSAFE')
    with tempfile.NamedTemporaryFile('w', dir=directory, delete=False) as stream:
        path = Path(stream.name)
        try:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
            path.replace(directory / 'cloudflare-discovery.json')
        finally:
            path.unlink(missing_ok=True)
