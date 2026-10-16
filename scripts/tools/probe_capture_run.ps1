param([string]$Macro, [string[]]$ArgList)
Remove-Item C:\temp-builder\OrCapstdout.txt, C:\temp-builder\OrCapstderr.txt -ErrorAction SilentlyContinue
$env:CDSHOME = "C:\Cadence\SPB_22.1"
$p = Start-Process -FilePath "C:\Cadence\SPB_22.1\tools\bin\Capture.exe" -ArgumentList $ArgList -WorkingDirectory C:\temp-builder -PassThru
"pid: $($p.Id)  args: $($ArgList -join ' | ')"
$prev = 10
foreach ($t in 10, 20, 30, 45, 60) {
    Start-Sleep -Seconds ($t - $prev)
    $prev = $t
    if ($p.HasExited) { "parent exited by ${t}s code=$($p.ExitCode)"; break }
    $procs = @(Get-Process -Name Capture -ErrorAction SilentlyContinue)
    "$t s: still running (count=$($procs.Count))"
}
if (-not $p.WaitForExit(5)) { $p.Kill() }
Get-Process -Name Capture -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
"=== OrCapstdout.txt ==="
if (Test-Path C:\temp-builder\OrCapstdout.txt) { Get-Content C:\temp-builder\OrCapstdout.txt -Raw } else { "(absent)" }
"=== OrCapstderr.txt ==="
if (Test-Path C:\temp-builder\OrCapstderr.txt) { Get-Content C:\temp-builder\OrCapstderr.txt -Raw } else { "(absent)" }
