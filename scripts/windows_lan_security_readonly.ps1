# Read-only security gate for the already-preflighted Master Windows 11 SMB host.
# No account, share, ACL, protocol, router or firewall modifications.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=LAN_SMB_SECURITY_READ_ONLY'
try {
    $phase = 'SMB1_FEATURE'
    Write-Output ('PHASE=' + $phase)
    try {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -ErrorAction Stop).State
        Write-Output ('SMB1_OPTIONAL_FEATURE_STATE=' + $state)
    } catch {
        Write-Output 'SMB1_OPTIONAL_FEATURE_STATE=NOT_VERIFIED'
    }

    $phase = 'SMB_SIGNING_POLICY'
    Write-Output ('PHASE=' + $phase)
    $reg = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters')
    if ($null -eq $reg) { throw 'SMB server parameters not readable' }
    try {
        $raw = $reg.GetValue('RequireSecuritySignature', $null)
        if ($null -eq $raw) {
            Write-Output 'SMB_SIGNING_REQUIRED_REGISTRY=UNSET'
        } else {
            Write-Output ('SMB_SIGNING_REQUIRED_REGISTRY=' + [string]$raw)
        }
    } finally { $reg.Close() }
    Write-Output 'SMB_SIGNING_EFFECTIVE=NOT_VERIFIED'
    Write-Output 'SMB_SHARE_ENCRYPTION_EFFECTIVE=NOT_VERIFIED'

    $phase = 'TARGET_ACL'
    Write-Output ('PHASE=' + $phase)
    $target = 'G:\GserverStorage\files'
    $acl = Get-Acl -LiteralPath $target -ErrorAction Stop
    $broadSids = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')
    $writeBits = [int64]0x000D0156
    $broadWrite = 0
    $unknownAcl = 0
    foreach ($entry in $acl.Access) {
        if ($entry.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
        $sid = $null
        try {
            $sid = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
        } catch {
            $unknownAcl += 1
        }
        if ($sid -in $broadSids -and (([int64]$entry.FileSystemRights -band $writeBits) -ne 0)) {
            $broadWrite += 1
        }
    }
    Write-Output ('BROAD_WRITE_ACE_COUNT=' + $broadWrite)
    Write-Output ('ACL_UNRESOLVED_IDENTITY_COUNT=' + $unknownAcl)
    Write-Output 'FIREWALL_445_REMOTE_SCOPE=NOT_VERIFIED'
    Write-Output 'ROUTER_WAN_445_FORWARD=NOT_VERIFIED'
    Write-Output 'WIFE_PC_SECURITY_PATCH_STATUS=NOT_VERIFIED'
    Write-Output 'CHANGES=NONE'
    Write-Output 'SMB_SHARE_CREATION=NOT_PERFORMED'
    $ok = $true
} catch {
    Write-Output ('FAILED_PHASE=' + $phase)
    Write-Output ('ERROR_TYPE=' + $_.Exception.GetType().Name)
    Write-Output 'CHANGES=NONE'
} finally {
    if ($ok) { Write-Output 'VERIFY=PASS' } else { Write-Output 'VERIFY=FAIL' }
    Write-Output 'PROJECT_END=Gserver'
    Write-Output '========== GACE_RESULT_END =========='
}
if (-not $ok) { exit 1 }
