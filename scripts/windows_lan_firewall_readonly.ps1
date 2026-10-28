# Read-only audit of existing inbound SMB firewall exposure on the Master host.
# No firewall, profile, router, share, credential or NTFS modifications.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=LAN_HOST_FIREWALL_445_READ_ONLY'
try {
    $phase = 'WINDOWS_FIREWALL_COM'
    Write-Output ('PHASE=' + $phase)
    $policy = New-Object -ComObject HNetCfg.FwPolicy2
    $inbound = 1
    $allow = 1
    $tcp = 6
    $private = 2
    $seen = 0
    $portAllows = 0
    $broadPrivate = 0
    $notPrivate = 0
    foreach ($rule in $policy.Rules) {
        $seen++
        if ($seen -gt 4000) { throw 'Firewall rule count exceeds bounded audit limit' }
        if (-not $rule.Enabled -or [int]$rule.Direction -ne $inbound -or
            [int]$rule.Action -ne $allow -or [int]$rule.Protocol -ne $tcp) { continue }
        $ports = [string]$rule.LocalPorts
        $matches445 = $false
        if ([string]::IsNullOrWhiteSpace($ports) -or $ports.Trim() -eq '*') {
            $matches445 = $true
        } else {
            foreach ($part in $ports.Split(',')) {
                $port = $part.Trim()
                if ($port -eq '445' -or $port -eq '0-65535' -or $port -eq '445-445') {
                    $matches445 = $true
                    break
                }
                if ($port -match '^(\d+)-(\d+)$') {
                    if ([int]$Matches[1] -le 445 -and [int]$Matches[2] -ge 445) {
                        $matches445 = $true
                        break
                    }
                }
            }
        }
        if (-not $matches445) { continue }
        $portAllows++
        $scope = [string]$rule.RemoteAddresses
        if ([string]::IsNullOrWhiteSpace($scope) -or $scope.Trim() -eq '*' -or
            $scope -match 'LocalSubnet|/|^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}-') {
            if (([int]$rule.Profiles -band $private) -ne 0 -or [int]$rule.Profiles -eq 2147483647) {
                $broadPrivate++
            }
        }
        if (([int]$rule.Profiles -band 5) -ne 0 -or [int]$rule.Profiles -eq 2147483647) {
            $notPrivate++
        }
    }
    Write-Output ('FIREWALL_RULES_INSPECTED=' + $seen)
    Write-Output ('ACTIVE_INBOUND_TCP445_ALLOW_RULES=' + $portAllows)
    Write-Output ('BROAD_SCOPE_PRIVATE_TCP445_ALLOW_RULES=' + $broadPrivate)
    Write-Output ('NONPRIVATE_TCP445_ALLOW_RULES=' + $notPrivate)
    Write-Output 'FIREWALL_445_EFFECTIVE_ACCESS=NOT_VERIFIED'
    Write-Output 'WIFE_PC_IPV4=NOT_VERIFIED'
    Write-Output 'ROUTER_WAN_FORWARD=NOT_VERIFIED'
    Write-Output 'CHANGES=NONE'
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
