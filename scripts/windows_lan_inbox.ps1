# Prepare an empty local-only Gserver LAN inbox; does NOT create a network share.
# Deliberately never edits G:\, GserverStorage, files, existing files or SMB settings.
param([switch]$Prepare)
$ErrorActionPreference = 'Stop'
$ok = $false
$phase = 'START'
$target = 'G:\GserverStorage\files\LAN-Inbox'
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=LAN_INBOX_LOCAL_ONLY'
try {
    $phase = 'SAFE_PARENT'
    Write-Output ('PHASE=' + $phase)
    foreach ($path in @('G:\', 'G:\GserverStorage', 'G:\GserverStorage\files')) {
        $item = Get-Item -LiteralPath $path -ErrorAction Stop
        if (-not $item.PSIsContainer) { throw 'Parent is not a directory' }
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse parent' }
    }
    $drive = New-Object IO.DriveInfo 'G:\'
    if ($drive.DriveFormat -ne 'NTFS') { throw 'NTFS drive required' }

    $phase = 'TARGET_COLLISION'
    Write-Output ('PHASE=' + $phase)
    if ([IO.Directory]::Exists($target) -or [IO.File]::Exists($target)) {
        # Never adopt or change an existing folder, including any inherited data.
        Write-Output 'INBOX_STATE=ALREADY_PRESENT_UNTOUCHED'
        Write-Output 'CHANGES=NONE'
        Write-Output 'REQUIRES_MANUAL_REVIEW=YES'
    } elseif (-not $Prepare) {
        Write-Output 'INBOX_STATE=ABSENT'
        Write-Output 'CHANGES=NONE'
        Write-Output 'NEXT=PREPARE_ALLOWED_BUT_NOT_EXECUTED'
        $ok = $true
    } else {
        $phase = 'CREATE_EMPTY_INBOX'
        Write-Output ('PHASE=' + $phase)
        [IO.Directory]::CreateDirectory($target) | Out-Null
        $phase = 'SET_CHILD_ACL'
        Write-Output ('PHASE=' + $phase)
        $acl = Get-Acl -LiteralPath $target -ErrorAction Stop
        $acl.SetAccessRuleProtection($true, $false)
        $ids = @(
            @{Sid='S-1-5-18'; Rights=[Security.AccessControl.FileSystemRights]::FullControl},
            @{Sid='S-1-5-32-544'; Rights=[Security.AccessControl.FileSystemRights]::FullControl},
            @{Sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value; Rights=[Security.AccessControl.FileSystemRights]::FullControl}
        )
        $inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
        foreach ($id in $ids) {
            $sid = [Security.Principal.SecurityIdentifier]::new($id.Sid)
            $rule = [Security.AccessControl.FileSystemAccessRule]::new($sid, $id.Rights, $inherit, [Security.AccessControl.PropagationFlags]::None, [Security.AccessControl.AccessControlType]::Allow)
            $acl.AddAccessRule($rule)
        }
        Set-Acl -LiteralPath $target -AclObject $acl -ErrorAction Stop
        $phase = 'READBACK'
        Write-Output ('PHASE=' + $phase)
        $saved = Get-Acl -LiteralPath $target -ErrorAction Stop
        if (-not $saved.AreAccessRulesProtected) { throw 'Inheritance protection not applied' }
        $broad = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')
        $broadWrite = 0
        foreach ($ace in $saved.Access) {
            if ($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { continue }
            $sid = $ace.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
            if ($sid -in $broad) { $broadWrite++ }
        }
        if ($broadWrite -ne 0) { throw 'Broad permissions remain in the new inbox' }
        Write-Output 'INBOX_STATE=CREATED'
        Write-Output 'INBOX_INHERITANCE_PROTECTED=True'
        Write-Output 'INBOX_BROAD_ALLOW_COUNT=0'
        Write-Output 'G_PARENT_ACL_CHANGED=False'
        Write-Output 'SHARE_CREATED=False'
        Write-Output 'FIREWALL_CHANGED=False'
        $ok = $true
    }
} catch {
    Write-Output ('FAILED_PHASE=' + $phase)
    Write-Output ('ERROR_TYPE=' + $_.Exception.GetType().Name)
    Write-Output 'INBOX_STATE=CHECK_REQUIRED_NO_AUTOMATIC_DELETE'
} finally {
    if ($ok) { Write-Output 'VERIFY=PASS' } else { Write-Output 'VERIFY=FAIL' }
    Write-Output 'PROJECT_END=Gserver'
    Write-Output '========== GACE_RESULT_END =========='
}
if (-not $ok) { exit 1 }
