# Read-only Windows-side F01 boot path audit. No task creation, WSL config, or service changes.
$ErrorActionPreference = 'Stop'
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=F01_WINDOWS_BOOT_READ_ONLY_AUDIT'
try {
    $wslTasks = @()
    foreach ($task in Get-ScheduledTask -ErrorAction SilentlyContinue) {
        foreach ($action in $task.Actions) {
            $exe = [string]$action.Execute
            $args = [string]$action.Arguments
            if ($exe -match '(?i)wsl' -or $args -match '(?i)\bwsl(\.exe)?\b') {
                $wslTasks += $task.TaskName
                break
            }
        }
    }
    $unique = $wslTasks | Sort-Object -Unique
    Write-Output ('WSL_DIRECT_SCHEDULED_TASK_COUNT=' + $unique.Count)
    if ($unique.Count -gt 0) {
        Write-Output ('WSL_DIRECT_SCHEDULED_TASKS=' + ($unique -join ';'))
    }
    Write-Output 'WSL_DISTRIBUTION_AUTOSTART=NOT_VERIFIED'
    Write-Output 'WINDOWS_REBOOT_RECOVERY=NOT_VERIFIED'
    Write-Output 'CHANGES=NONE'
    Write-Output 'VERIFY=PASS'
    exit 0
}
catch {
    Write-Output ('AUDIT_ERROR=' + $_.Exception.GetType().FullName)
    Write-Output 'CHANGES=NONE'
    Write-Output 'VERIFY=FAIL'
    exit 1
}
finally {
    Write-Output 'PROJECT_END=Gserver'
    Write-Output '========== GACE_RESULT_END =========='
}
