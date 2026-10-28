# Narrow Gserver ACL readback; no user names, IPs, passwords or mutations.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=G_DRIVE_SMB_ACL_DETAIL_READ_ONLY'
try {
    $target = 'G:\GserverStorage\files'
    $phase = 'DRIVE_FORMAT'
    Write-Output ('PHASE=' + $phase)
    try {
        $drive = New-Object System.IO.DriveInfo 'G:\'
        Write-Output ('G_FILESYSTEM=' + $drive.DriveFormat)
    } catch {
        Write-Output 'G_FILESYSTEM=NOT_VERIFIED'
    }

    $broadSids = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')
    $sidLabels = @{
        'S-1-1-0' = 'EVERYONE'
        'S-1-5-11' = 'AUTHENTICATED_USERS'
        'S-1-5-32-545' = 'BUILTIN_USERS'
    }
    $writeBits = [int64]0x000D0156
    foreach ($scope in @('PARENT', 'FILES')) {
        $phase = 'ACL_' + $scope
        Write-Output ('PHASE=' + $phase)
        $path = if ($scope -eq 'FILES') { $target } else { 'G:\GserverStorage' }
        $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
        Write-Output ($scope + '_INHERITANCE_PROTECTED=' + [bool]$acl.AreAccessRulesProtected)
        $count = 0
        $unresolved = 0
        foreach ($entry in $acl.Access) {
            if ($entry.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow) { continue }
            $sid = $null
            try {
                $sid = $entry.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
            } catch {
                $unresolved++
                continue
            }
            if ($sid -notin $broadSids) { continue }
            if (([int64]$entry.FileSystemRights -band $writeBits) -eq 0) { continue }
            $count++
            Write-Output ($scope + '_BROAD_WRITE_' + $count + '_GROUP=' + $sidLabels[$sid])
            Write-Output ($scope + '_BROAD_WRITE_' + $count + '_INHERITED=' + [bool]$entry.IsInherited)
            Write-Output ($scope + '_BROAD_WRITE_' + $count + '_RIGHTS=' + $entry.FileSystemRights.ToString())
        }
        Write-Output ($scope + '_BROAD_WRITE_COUNT=' + $count)
        Write-Output ($scope + '_UNRESOLVED_ACE_COUNT=' + $unresolved)
    }
    Write-Output 'SHARE_AND_NTFS_EFFECTIVE_ACCESS=NOT_VERIFIED'
    Write-Output 'CHANGES=NONE'
    Write-Output 'LAN_SHARE=NOT_CREATED_BY_THIS_CHECK'
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
