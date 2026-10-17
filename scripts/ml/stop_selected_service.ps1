# Stops only this task's recorded Python HTTP model process; never removes files.
# Run manually when LAN inference is no longer needed. Not executed on startup.
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param()
$ErrorActionPreference = 'Stop'
$taskRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$taskRuntimePath = Join-Path $taskRepo 'ml\lan_inference\selected-20261017-v1\runtime.json'
$taskRuntime = Get-Content -LiteralPath $taskRuntimePath -Raw | ConvertFrom-Json
$taskPid = [int]$taskRuntime.pid
$taskProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $taskPid"
if ($null -eq $taskProcess) { Write-Output 'Recorded inference process is already stopped.'; return }
$taskExpectedScript = Join-Path $taskRepo 'scripts\ml\serve_selected.py'
if ($taskProcess.Name -notmatch '^python(w)?\.exe$' -or
    $taskProcess.CommandLine.IndexOf($taskExpectedScript, [StringComparison]::OrdinalIgnoreCase) -lt 0 -or
    $taskProcess.CommandLine.IndexOf($taskRuntimePath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'PID belongs to a different process; refusing to stop it.'
}
if ($PSCmdlet.ShouldProcess("AEGIS selected LAYA HTTP inference PID $taskPid", 'Stop process')) {
    Stop-Process -Id $taskPid -ErrorAction Stop
}
