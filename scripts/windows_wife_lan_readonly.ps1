# Identify OS generation and LAN IPv4 candidates on the local Windows host.
# Run on the intended client PC. Read-only; never changes shares or settings.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=WINDOWS_LAN_CLIENT_IDENTITY_READ_ONLY'
try {
    $phase = 'WINDOWS_VERSION'
    Write-Output ('PHASE=' + $phase)
    $key = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion')
    if ($null -eq $key) { throw 'Windows version registry unavailable' }
    try {
        $buildText = [string]$key.GetValue('CurrentBuild', 'UNKNOWN')
        $revision = [string]$key.GetValue('UBR', 'UNKNOWN')
        $release = [string]$key.GetValue('DisplayVersion', 'UNKNOWN')
        $legacyName = [string]$key.GetValue('ProductName', 'UNKNOWN')
    } finally { $key.Close() }
    $build = 0
    if (-not [int]::TryParse($buildText, [ref]$build)) { throw 'Windows build not numeric' }
    $generation = if ($build -ge 22000) { 'WINDOWS_11_FAMILY' } else { 'WINDOWS_10_OR_EARLIER' }
    Write-Output ('OS_FAMILY_BY_BUILD=' + $generation)
    Write-Output ('WINDOWS_RELEASE=' + $release)
    Write-Output ('WINDOWS_BUILD=' + $buildText + '.' + $revision)
    Write-Output ('REGISTRY_PRODUCT_NAME_LEGACY=' + $legacyName)
    Write-Output 'OS_FAMILY_BY_BUILD_IS_NOT_A_MACHINE_IDENTITY=YES'
    Write-Output 'ESU_ENROLLMENT=NOT_VERIFIED'
    Write-Output 'PATCH_CURRENCY=NOT_VERIFIED'

    $phase = 'LOCAL_GSERVER_MARKERS'
    Write-Output ('PHASE=' + $phase)
    $repoMarker = [IO.File]::Exists('G:\Project\Gserver\repository\AGENTS.md')
    $inboxMarker = [IO.Directory]::Exists('G:\GserverStorage\files\LAN-Inbox')
    if ($repoMarker -and $inboxMarker) {
        Write-Output 'MASTER_GSERVER_MARKERS=BOTH_PRESENT'
        Write-Output 'HOST_ROLE_HINT=LIKELY_MASTER_GSERVER'
    } else {
        Write-Output 'MASTER_GSERVER_MARKERS=NOT_BOTH_PRESENT'
        Write-Output 'HOST_ROLE_HINT=UNIDENTIFIED'
    }
    Write-Output 'HOST_IDENTITY=NOT_CRYPTOGRAPHICALLY_VERIFIED'

    $phase = 'LAN_IPV4'
    Write-Output ('PHASE=' + $phase)
    $addresses = @()
    $virtualAddresses = 0
    foreach ($nic in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        if ($nic.OperationalStatus -ne [Net.NetworkInformation.OperationalStatus]::Up) { continue }
        if ($nic.NetworkInterfaceType -eq [Net.NetworkInformation.NetworkInterfaceType]::Loopback -or
            $nic.NetworkInterfaceType -eq [Net.NetworkInformation.NetworkInterfaceType]::Tunnel) { continue }
        $virtual = ($nic.Name -match 'vEthernet|WSL|Hyper-V|VirtualBox|VMware|Docker|TAP|Tailscale|WireGuard|ZeroTier') -or
            ($nic.Description -match 'Hyper-V|VirtualBox|VMware|Docker|WSL|TAP|Tailscale|WireGuard|ZeroTier')
        foreach ($entry in $nic.GetIPProperties().UnicastAddresses) {
            $ip = $entry.Address
            if ($ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { continue }
            $bytes = $ip.GetAddressBytes()
            $rfc1918 = ($bytes[0] -eq 10) -or
                ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
                ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
            if (-not $rfc1918) { continue }
            if ($virtual) {
                $virtualAddresses++
                continue
            }
            if ($ip.ToString() -notin $addresses) { $addresses += $ip.ToString() }
        }
    }
    foreach ($ip in $addresses) { Write-Output ('LAN_IPV4_CANDIDATE=' + $ip) }
    Write-Output ('LAN_IPV4_CANDIDATES=' + $addresses.Count)
    Write-Output ('VIRTUAL_INTERFACE_IPV4_CANDIDATES_SKIPPED=' + $virtualAddresses)

    $phase = 'NETWORK_PROFILE'
    Write-Output ('PHASE=' + $phase)
    try {
        $profiles = @(Get-NetConnectionProfile -ErrorAction Stop | Where-Object {
            $_.IPv4Connectivity -ne 'Disconnected' -and $_.IPv4Connectivity -ne 'NoTraffic'
        })
        Write-Output ('ACTIVE_PRIVATE_PROFILES=' + @($profiles | Where-Object { $_.NetworkCategory -eq 'Private' }).Count)
        Write-Output ('ACTIVE_PUBLIC_PROFILES=' + @($profiles | Where-Object { $_.NetworkCategory -eq 'Public' }).Count)
    } catch {
        Write-Output 'NETWORK_PROFILES=NOT_VERIFIED'
    }
    Write-Output 'SMB3_NEGOTIATED=NOT_VERIFIED'
    Write-Output 'SMB_ENCRYPTED_SESSION=NOT_VERIFIED'
    Write-Output 'SOURCE_FILES_UNCHANGED=True'
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
