# Scoped read-only TCP445 Windows Firewall audit. Does not infer effective access.
# No modifications to firewall, shares, accounts, drives, router or Docker.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=LAN_HOST_FIREWALL_445_SCOPED_READ_ONLY'
try {
    $phase = 'FIREWALL_COM_RULES'
    Write-Output ('PHASE=' + $phase)
    $policy = New-Object -ComObject HNetCfg.FwPolicy2
    $seen = 0
    $explicit445 = 0
    $explicitPrivate = 0
    $explicitPrivateBroad = 0
    $explicitNonprivate = 0
    $explicitRestrictedAppService = 0
    $anyPortGeneric = 0
    $anyPortAppService = 0
    $unknownPortScope = 0
    foreach ($rule in $policy.Rules) {
        $seen++
        if ($seen -gt 4000) { throw 'Firewall audit safety limit exceeded' }
        if (-not $rule.Enabled) { continue }
        if ([int]$rule.Direction -ne 1 -or [int]$rule.Action -ne 1) { continue }
        $protocol = [int]$rule.Protocol
        if ($protocol -ne 6 -and $protocol -ne 256) { continue }

        $ports = ''
        try { $ports = [string]$rule.LocalPorts }
        catch {
            $unknownPortScope++
            continue
        }
        $isAnyPort = [string]::IsNullOrWhiteSpace($ports) -or $ports.Trim() -eq '*'
        $has445 = $false
        if (-not $isAnyPort) {
            foreach ($item in $ports.Split(',')) {
                $value = $item.Trim()
                if ($value -eq '445') { $has445 = $true; break }
                if ($value -match '^[0-9]+-[0-9]+$') {
                    $bounds = $value.Split('-')
                    if ([int]$bounds[0] -le 445 -and [int]$bounds[1] -ge 445) {
                        $has445 = $true
                        break
                    }
                }
            }
        }

        $app = [string]$rule.ApplicationName
        $service = [string]$rule.ServiceName
        $restricted = (-not [string]::IsNullOrWhiteSpace($app) -and $app -ne '*') -or
            (-not [string]::IsNullOrWhiteSpace($service) -and $service -ne '*')
        if ($isAnyPort -or $protocol -eq 256) {
            # Generic rules cannot be counted as explicit SMB permissions.
            if ($restricted) { $anyPortAppService++ } else { $anyPortGeneric++ }
            continue
        }
        if (-not $has445) { continue }
        $explicit445++
        if ($restricted) { $explicitRestrictedAppService++ }

        $profiles = [int]$rule.Profiles
        $private = (($profiles -band 2) -ne 0) -or $profiles -eq 2147483647 -or $profiles -eq -1
        $nonprivate = (($profiles -band 5) -ne 0) -or $profiles -eq 2147483647 -or $profiles -eq -1
        if ($private) {
            $explicitPrivate++
            $scope = [string]$rule.RemoteAddresses
            $oneIPv4 = $scope -match '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'
            if (-not $oneIPv4) { $explicitPrivateBroad++ }
        }
        if ($nonprivate) { $explicitNonprivate++ }
    }
    Write-Output ('FIREWALL_RULES_INSPECTED=' + $seen)
    Write-Output ('EXPLICIT_TCP445_ALLOW_RULES=' + $explicit445)
    Write-Output ('EXPLICIT_TCP445_PRIVATE_ALLOW_RULES=' + $explicitPrivate)
    Write-Output ('EXPLICIT_TCP445_PRIVATE_NON_SINGLE_IP_RULES=' + $explicitPrivateBroad)
    Write-Output ('EXPLICIT_TCP445_NONPRIVATE_ALLOW_RULES=' + $explicitNonprivate)
    Write-Output ('EXPLICIT_TCP445_APP_SERVICE_RESTRICTED=' + $explicitRestrictedAppService)
    Write-Output ('GENERIC_ANYPORT_APP_SERVICE_RESTRICTED=' + $anyPortAppService)
    Write-Output ('GENERIC_ANYPORT_OTHER=' + $anyPortGeneric)
    Write-Output ('UNKNOWN_PORT_SCOPE_RULES=' + $unknownPortScope)
    Write-Output 'NOTE=COUNTS_ARE_RULES_NOT_PROOF_OF_SMB_REACHABILITY'
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
