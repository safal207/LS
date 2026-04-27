# Seed ghostgpt-ls-landing/.env and start Reflection (8780) + HCP (8781).
#
# Usage (repo root):
#   .\scripts\dev_landing_stack.ps1                      # two API windows
#   .\scripts\dev_landing_stack.ps1 -SingleProcess         # one window, one Python process
#   .\scripts\dev_landing_stack.ps1 -HcpWithBootstrap      # HCP with PluginManager (load button)
param(
    [switch] $HcpWithBootstrap,
    [switch] $SingleProcess
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$pyPath = "$root;$root\python" -replace '/', '\'

$landing = Join-Path $root "ghostgpt-ls-landing"
$envExample = Join-Path $landing ".env.example"
$envLocal = Join-Path $landing ".env"
if (Test-Path $envExample) {
    if (-not (Test-Path $envLocal)) {
        Copy-Item -Path $envExample -Destination $envLocal
        Write-Host "Created $envLocal from .env.example" -ForegroundColor Green
    }
    else {
        Write-Host ".env already exists — left unchanged: $envLocal" -ForegroundColor DarkYellow
    }
}

if ($SingleProcess) {
    $stackCmd = "Set-Location '$root'; `$env:PYTHONPATH='$pyPath'; python '$root\scripts\run_dev_stack_api.py'"
    if ($HcpWithBootstrap) {
        $mainPy = Join-Path $root "apps\console\main.py"
        $stackCmd += " --bootstrap '$mainPy'"
    }
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $stackCmd)
    Write-Host ""
    Write-Host "Single-process API window started (Reflection 8780 + HCP 8781)." -ForegroundColor Cyan
    if ($HcpWithBootstrap) { Write-Host "  HCP PluginManager: ON" -ForegroundColor Cyan }
}
else {
    $reflectCmd = "Set-Location '$root'; `$env:PYTHONPATH='$root'; python '$root\scripts\run_reflection_dashboard_api.py' --port 8780"
    $hcpScript = "python '$root\scripts\run_hcp_marketplace_api.py' --port 8781"
    if ($HcpWithBootstrap) {
        $mainPy = Join-Path $root "apps\console\main.py"
        $hcpScript = "python '$root\scripts\run_hcp_marketplace_api.py' --port 8781 --bootstrap '$mainPy'"
    }
    $hcpCmd = "Set-Location '$root'; `$env:PYTHONPATH='$pyPath'; " + $hcpScript
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $reflectCmd)
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $hcpCmd)
    Write-Host ""
    Write-Host "API windows started." -ForegroundColor Cyan
    if ($HcpWithBootstrap) { Write-Host "  HCP PluginManager: ON" -ForegroundColor Cyan }
}

Write-Host "  Reflection: http://127.0.0.1:8780"
Write-Host "  HCP:        http://127.0.0.1:8781"
Write-Host ""
Write-Host "Next:  cd ghostgpt-ls-landing" -ForegroundColor White
Write-Host "       npm run dev" -ForegroundColor White
Write-Host ""
