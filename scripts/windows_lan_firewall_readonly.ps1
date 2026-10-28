# Read-only, bounded audit of inbound TCP445 allow rules on Master Windows.
# Does not change firewall, shares, accounts, network profiles or permissions.
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
    $seen = 0
    $tcpAllows = 0
    $broadPrivate = 0
    $nonPrivate = 0
    $unknownPorts = 0
    foreach ($rule in $policy.Rules) {
        $seen++
        if ($seen -gt 4000) { throw 'Firewall rule scan limit exceeded' }
        if (-not $rule.Enabled) { continue }
        if ([int]$rule.Direction -ne 1 -or [int]$rule.Action -ne 1) { continue }
        if ([int]$rule.Protocol -ne 6 -and [int]$rule.Protocol -ne 256) { continue }

        # Count only rules that can allow TCP/445. Unreadable port scope is unknown.
        $portText = ''
        try {
            $portText = [string]$rule.LocalPorts
        } catch {
            $unknownPorts++
            continue
        }
        $is445 = [string]::IsNullOrWhiteSpace($portText) -or $portText.Trim() -eq '*'
        if (-not $is445) {
            foreach ($item in $portText.Split(',')) {
                $item = $item.Trim()
                if ($item -eq '445') {
                    $is445 = $true
                    break
                }
                if ($item -match '^[0-9]+-[0-9]+$') {
                    $bounds = $item.Split('-')
                    if ([int]$bounds[0] -le 445 -and [int]$bounds[1] -ge 445) {
                        $is445 = $true
                        break
                    }
                }
            }
        }
        if (-not $is445) { continue }
        $tcpAllows++

        # A single IPv4 address is narrow; wildcard, subnet and aliases are not.
        $scope = [string]$rule.RemoteAddresses
        $singleIPv4 = $scope -match '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
        $profiles = [int]$rule.Profiles
        if (-not $singleIPv4 -and (($profiles -band 2) -ne 0 -or $profiles -eq 2147483647)) {
            $broadPrivate++
        }
        if (($profiles -band 5) -ne 0 -or $profiles -eq 2147483647) {
            $nonPrivate++
        }
    }
    Write-Output ('FIREWALL_RULES_INSPECTED=' + $seen)
    Write-Output ('ACTIVE_INBOUND_TCP445_ALLOW_RULES=' + $tcpAllows)
    Write-Output ('BROAD_SCOPE_PRIVATE_TCP445_ALLOW_RULES=' + $broadPrivate)
    Write-Output ('NONPRIVATE_TCP445_ALLOW_RULES=' + $nonPrivate)
    Write-Output ('UNREADABLE_ALLOW_RULE_PORT_SCOPES=' + $unknownPorts)
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
