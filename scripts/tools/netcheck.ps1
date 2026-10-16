[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$wc = New-Object System.Net.WebClient
$wc.Proxy = New-Object System.Net.WebProxy('http://172.16.205.246:9090')
try {
  $s = $wc.DownloadString('https://registry.npmjs.org/playwright-core/latest')
  Write-Host "PROXY-OK first 120 chars:" $s.Substring(0, [Math]::Min(120, $s.Length))
} catch {
  Write-Host "PROXY-FAIL" $_.Exception.Message
}
try {
  $d = $wc.DownloadString('https://pypi.org/simple/mcp/')
  Write-Host "PYPI-OK length" $d.Length
} catch {
  Write-Host "PYPI-FAIL" $_.Exception.Message
}
