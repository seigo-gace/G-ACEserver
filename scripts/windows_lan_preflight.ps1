# Gserver single-user Windows SMB LAN transfer readiness - read only.
# Run on Master Windows 11 host. No settings, firewall, account or share changes.
$ErrorActionPreference = 'Stop'
$verified = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=WINDOWS_LAN_SMB_READ_ONLY_PREFLIGHT'
try {
    $target = 'G:\GserverStorage\files'
    $folder = Get-Item -LiteralPath $target -ErrorAction Stop
    if (-not $folder.PSIsContainer) { throw 'Storage target is not a directory' }
    $reparse = [System.IO.FileAttributes]::ReparsePoint
    if (($folder.Attributes -band $reparse) -ne 0) { throw 'Storage target is a reparse point' }
    $parent = Get-Item -LiteralPath 'G:\GserverStorage' -ErrorAction Stop
    if (($parent.Attributes -band $reparse) -ne 0) { throw 'Storage parent is a reparse point' }

    Write-Output 'TARGET=G:\GserverStorage\files'
    Write-Output 'TARGET_DIRECTORY=YES'
    $serverService = Get-Service -Name 'LanmanServer' -ErrorAction Stop
    Write-Output ('SMB_SERVER_SERVICE=' + $serverService.Status)
    $config = Get-SmbServerConfiguration -ErrorAction Stop
    Write-Output ('SMB2_ENABLED=' + [bool]$config.EnableSMB2Protocol)
    Write-Output ('SMB1_ENABLED=' + [bool]$config.EnableSMB1Protocol)
    Write-Output ('SMB_REJECT_UNENCRYPTED=' + [bool]$config.RejectUnencryptedAccess)

    $profiles = @(Get-NetConnectionProfile -ErrorAction Stop | Where-Object {
        $_.IPv4Connectivity -ne 'Disconnected' -and
        $_.IPv4Connectivity -ne 'NoTraffic'
    })
    $privateCount = @($profiles | Where-Object { $_.NetworkCategory -eq 'Private' }).Count
    $publicCount = @($profiles | Where-Object { $_.NetworkCategory -eq 'Public' }).Count
    Write-Output ('ACTIVE_PRIVATE_PROFILES=' + $privateCount)
    Write-Output ('ACTIVE_PUBLIC_PROFILES=' + $publicCount)

    $reserved = @(Get-SmbShare -Name 'GserverTransfer' -ErrorAction SilentlyContinue)
    Write-Output ('GSERVER_SHARE_NAME_IN_USE=' + [bool]($reserved.Count -gt 0))
    $sameFolderShares = @(Get-SmbShare -ErrorAction Stop | Where-Object {
        $_.Path -and [string]::Equals($_.Path.TrimEnd('\'), $target, [System.StringComparison]::OrdinalIgnoreCase)
    })
    Write-Output ('TARGET_ALREADY_SHARED=' + [bool]($sameFolderShares.Count -gt 0))
    $serverPort = @(Get-NetTCPConnection -State Listen -LocalPort 445 -ErrorAction SilentlyContinue)
    Write-Output ('SMB_445_LISTENING=' + [bool]($serverPort.Count -gt 0))

    Write-Output 'CHANGES=NONE'
    Write-Output 'LAN_FILE_TRANSFER=NOT_ENABLED_BY_THIS_CHECK'
    $verified = $true
} catch {
    Write-Output ('ERROR_TYPE=' + $_.Exception.GetType().Name)
    Write-Output 'CHANGES=NONE'
} finally {
    if ($verified) { Write-Output 'VERIFY=PASS' } else { Write-Output 'VERIFY=FAIL' }
    Write-Output 'PROJECT_END=Gserver'
    Write-Output '========== GACE_RESULT_END =========='
}
if (-not $verified) { exit 1 }
