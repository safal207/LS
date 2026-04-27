# Start Reflection (8780) and HCP (8781) in new windows; seed ghostgpt-ls-landing/.env from .env.example.
# Usage (repo root):  .\scripts\dev_landing_stack.ps1
# Optional:  .\scripts\dev_landing_stack.ps1 -HcpWithBootstrap
param(
    [switch] $HcpWithBootstrap
)
$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

$reflectCmd = "Set-Location '$root'; `$env:PYTHONPATH='$root'; python '$root\scripts\run_reflection_dashboard_api.py' --port 8780"
$pyPathHcp = "$root;$root\python" -replace '/', '\'
$hcpScript = "python '$root\scripts\run_hcp_marketplace_api.py' --port 8781"
if ($HcpWithBootstrap) {
    $mainPy = Join-Path $root "apps\console\main.py"
    $hcpScript = "python '$root\scripts\run_hcp_marketplace_api.py' --port 8781 --bootstrap '$mainPy'"
}
$hcpCmd = "Set-Location '$root'; `$env:PYTHONPATH='$pyPathHcp'; " + $hcpScript

Start-Process powershell -ArgumentList @("-NoExit", "-Command", $reflectCmd)
Start-Process powershell -ArgumentList @("-NoExit", "-Command", $hcpCmd)

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

Write-Host ""
Write-Host "API windows started." -ForegroundColor Cyan
Write-Host "  Reflection: http://127.0.0.1:8780"
Write-Host "  HCP:        http://127.0.0.1:8781"
if ($HcpWithBootstrap) { Write-Host "  HCP:        PluginManager ON (load button)" -ForegroundColor Cyan }
Write-Host ""
Write-Host "Next:  cd ghostgpt-ls-landing" -ForegroundColor White
Write-Host "       npm run dev" -ForegroundColor White
Write-Host ""
