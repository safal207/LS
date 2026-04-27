# Start Reflection Dashboard API on :8780 (for ghostgpt-ls-landing with VITE_REFLECTION_API_BASE).
# From repo root:  .\scripts\run_reflection_dashboard_dev.ps1
# In another terminal:  cd ghostgpt-ls-landing; npm run dev
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONPATH = $root
python (Join-Path $root "scripts\run_reflection_dashboard_api.py") @args
