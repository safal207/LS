param(
    [string]$RepoDir = "",
    [switch]$SkipUpdate
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.liminalqa.local"
$exampleEnvFile = Join-Path $repoRoot ".env.liminalqa.local.example"
$composeFile = Join-Path $repoRoot "deploy/liminalqa-local.compose.yml"

function Get-EnvMap {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $parts = $trimmed -split "=", 2
        if ($parts.Length -eq 2) {
            $values[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
    return $values
}

$envMap = Get-EnvMap -Path $envFile
if (-not $RepoDir) {
    $repoSetting = $envMap["LIMINALQA_REPO_DIR"]
    if (-not $repoSetting) {
        $repoSetting = "..\LiminalQAengineer"
    }
    $RepoDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $repoSetting))
}

if (-not (Test-Path $envFile) -and (Test-Path $exampleEnvFile)) {
    Copy-Item $exampleEnvFile $envFile
    Write-Host "Created local env file: $envFile"
}

if (-not (Test-Path $RepoDir)) {
    git clone --depth 1 https://github.com/safal207/LiminalQAengineer.git $RepoDir
} elseif (-not $SkipUpdate) {
    git -C $RepoDir fetch origin main
    git -C $RepoDir pull --ff-only origin main
}

if (-not (Test-Path $composeFile)) {
    throw "Missing compose file: $composeFile"
}

$env:LIMINALQA_REPO_DIR = $RepoDir
if ($envMap["LIMINALQA_TOKEN"]) {
    $env:LIMINALQA_TOKEN = $envMap["LIMINALQA_TOKEN"]
}

docker compose --env-file $envFile -f $composeFile up -d

$healthUrl = if ($envMap["LIMINALQA_URL"]) { $envMap["LIMINALQA_URL"].TrimEnd("/") + "/health" } else { "http://localhost:8088/health" }
$deadline = (Get-Date).AddMinutes(8)

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 5
        Write-Host ""
        Write-Host "LiminalQA is healthy."
        $response | ConvertTo-Json -Depth 5
        Write-Host ""
        Write-Host "Local URL: $($healthUrl -replace '/health$','')"
        exit 0
    } catch {
        Start-Sleep -Seconds 3
    }
}

throw "LiminalQA did not become healthy within 8 minutes: $healthUrl"
