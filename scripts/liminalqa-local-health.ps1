param(
    [string]$Url = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.liminalqa.local"

if (-not $Url -and (Test-Path $envFile)) {
    foreach ($line in Get-Content $envFile) {
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("LIMINALQA_URL=")) {
            $Url = ($trimmed -split "=", 2)[1].Trim()
            break
        }
    }
}

if (-not $Url) {
    $Url = "http://localhost:8088"
}

$healthUrl = $Url.TrimEnd("/") + "/health"
$response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 10
$response | ConvertTo-Json -Depth 5
