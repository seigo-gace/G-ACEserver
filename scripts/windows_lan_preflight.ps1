# Gserver LAN readiness: read-only, bounded, no full SMB share enumeration.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=WINDOWS_LAN_SMB_LIGHTWEIGHT_PREFLIGHT'
try {
    $phase = 'TARGET'
    Write-Output ('PHASE=' + $phase)
    $target = 'G:\GserverStorage\files'
    if (-not [System.IO.Directory]::Exists($target)) { throw 'Storage directory absent' }
    foreach ($p in @('G:\GserverStorage', $target)) {
        if (([System.IO.File]::GetAttributes($p) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Storage directory uses reparse point'
        }
    }
    Write-Output 'TARGET_DIRECTORY=YES'

    $phase = 'SMB_SERVICE'
    Write-Output ('PHASE=' + $phase)
    $service = Get-Service -Name 'LanmanServer' -ErrorAction Stop
    Write-Output ('SMB_SERVER_SERVICE=' + $service.Status)

    $phase = 'SMB_PROTOCOL_REGISTRY'
    Write-Output ('PHASE=' + $phase)
    $key = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters')
    if ($null -eq $key) { throw 'SMB parameters key unavailable' }
    try {
        foreach ($name in @('SMB1', 'SMB2')) {
            $value = $key.GetValue($name, $null)
            if ($null -eq $value) { $state = 'REGISTRY_UNSET' }
            else { $state = [string]$value }
            Write-Output ($name + '_REGISTRY_VALUE=' + $state)
        }
    } finally {
        $key.Close()
    }

    $phase = 'NETWORK_PROFILE'
    Write-Output ('PHASE=' + $phase)
    $network = @(Get-NetConnectionProfile -ErrorAction Stop)
    $privateCount = @($network | Where-Object { $_.NetworkCategory -eq 'Private' }).Count
    $publicCount = @($network | Where-Object { $_.NetworkCategory -eq 'Public' }).Count
    Write-Output ('PRIVATE_PROFILES=' + $privateCount)
    Write-Output ('PUBLIC_PROFILES=' + $publicCount)

    $phase = 'SHARE_NAME'
    Write-Output ('PHASE=' + $phase)
    # Read one exact registry value; absent shares must not generate native stderr.
    # Avoid net.exe/PowerShell 5.1 NativeCommandError and unbounded CIM share scans.
    $shares = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Services\LanmanServer\Shares')
    if ($null -eq $shares) {
        Write-Output 'GSERVER_SHARE_NAME_IN_USE=UNKNOWN'
        Write-Output 'SHARE_REGISTRY=UNAVAILABLE'
    } else {
        try {
            $reserved = $null -ne $shares.GetValue('GserverTransfer', $null)
            Write-Output ('GSERVER_SHARE_NAME_IN_USE=' + [bool]$reserved)
        } finally {
            $shares.Close()
        }
    }

    $phase = 'PORT_445'
    Write-Output ('PHASE=' + $phase)
    $listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $listening = @($listeners | Where-Object { $_.Port -eq 445 }).Count -gt 0
    Write-Output ('SMB_445_LISTENING=' + $listening)

    $ok = $true
    Write-Output 'CHANGES=NONE'
    Write-Output 'LAN_FILE_TRANSFER=NOT_ENABLED_BY_THIS_CHECK'
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
