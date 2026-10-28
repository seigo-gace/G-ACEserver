# Run on the wife's Windows PC, read only. No user names, MACs or secrets.
$ErrorActionPreference = 'Stop'
$phase = 'START'
$ok = $false
Write-Output '========== GACE_RESULT_BEGIN =========='
Write-Output 'PROJECT=Gserver'
Write-Output 'ACTION=WIFE_PC_LAN_READ_ONLY'
try {
    $phase = 'WINDOWS_VERSION'
    Write-Output ('PHASE=' + $phase)
    $key = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion')
    if ($null -eq $key) { throw 'Windows version registry unavailable' }
    try {
        $build = [string]$key.GetValue('CurrentBuild', 'UNKNOWN')
        $revision = [string]$key.GetValue('UBR', 'UNKNOWN')
        $release = [string]$key.GetValue('DisplayVersion', 'UNKNOWN')
        $product = [string]$key.GetValue('ProductName', 'UNKNOWN')
        Write-Output ('WINDOWS_PRODUCT=' + $product)
        Write-Output ('WINDOWS_RELEASE=' + $release)
        Write-Output ('WINDOWS_BUILD=' + $build + '.' + $revision)
    } finally { $key.Close() }
    Write-Output 'ESU_ENROLLMENT=NOT_VERIFIED'
    Write-Output 'PATCH_ELIGIBILITY=NOT_VERIFIED'

    $phase = 'ACTIVE_PRIVATE_IPV4'
    Write-Output ('PHASE=' + $phase)
    $addresses = @()
    foreach ($nic in [Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        if ($nic.OperationalStatus -ne [Net.NetworkInformation.OperationalStatus]::Up) { continue }
        if ($nic.NetworkInterfaceType -eq [Net.NetworkInformation.NetworkInterfaceType]::Loopback -or
            $nic.NetworkInterfaceType -eq [Net.NetworkInformation.NetworkInterfaceType]::Tunnel) { continue }
        foreach ($entry in $nic.GetIPProperties().UnicastAddresses) {
            $ip = $entry.Address
            if ($ip.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork) { continue }
            $bytes = $ip.GetAddressBytes()
            $isRfc1918 = ($bytes[0] -eq 10) -or
                ($bytes[0] -eq 172 -and $bytes[1] -ge 16 -and $bytes[1] -le 31) -or
                ($bytes[0] -eq 192 -and $bytes[1] -eq 168)
            if ($isRfc1918 -and $ip.ToString() -notin $addresses) {
                $addresses += $ip.ToString()
            }
        }
    }
    foreach ($ip in $addresses) { Write-Output ('LAN_IPV4_CANDIDATE=' + $ip) }
    Write-Output ('LAN_IPV4_CANDIDATES=' + $addresses.Count)
    Write-Output 'PRIVATE_NETWORK_PROFILE=NOT_VERIFIED'
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
