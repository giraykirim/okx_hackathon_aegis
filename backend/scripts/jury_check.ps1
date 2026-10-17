# Rebuild actual local jury evidence. Requires the MARKET_ONLY server on localhost:8000.
# No secrets are printed; the proof scripts keep credentials in process memory.
$ErrorActionPreference = 'Stop'
$backendPath = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
$ruffPath = Join-Path $backendPath '.venv\Scripts\ruff.exe'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
$health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health'
if ($health.source_mode -ne 'MARKET_ONLY' -or $health.running -or $health.live_execution_enabled) {
    throw 'Requires MARKET_ONLY with the agent stopped and live execution disabled.'
}
Push-Location $backendPath
try {
    & $pythonPath -m pytest -q --junitxml=evidence/tests.xml
    if ($LASTEXITCODE) { throw 'pytest failed' }
    & $ruffPath check .
    if ($LASTEXITCODE) { throw 'Ruff lint failed' }
    & $ruffPath format --check .
    if ($LASTEXITCODE) { throw 'Ruff formatting failed' }
    foreach ($module in @('scripts.export_contract', 'scripts.prove', 'scripts.http_smoke',
                          'scripts.prove_service', 'scripts.build_manifest')) {
        if ($module -eq 'scripts.export_contract') { & $pythonPath -m $module --check }
        else { & $pythonPath -m $module }
        if ($LASTEXITCODE) { throw "Verification failed: $module" }
    }
    Write-Output 'PASS: current local evidence rebuilt; see evidence/jury-manifest.json.'
    Write-Output 'Public deployment, authenticated models and Fuji remain NOT_TESTED.'
} finally {
    Pop-Location
}
