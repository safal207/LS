param(
    [string]$RepoDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.liminalqa.local"
$composeFile = Join-Path $repoRoot "deploy/liminalqa-local.compose.yml"

if (-not $RepoDir -and (Test-Path $envFile)) {
    foreach ($line in Get-Content $envFile) {
        $trimmed = $line.Trim()
        if ($trimmed.StartsWith("LIMINALQA_REPO_DIR=")) {
            $RepoDir = ($trimmed -split "=", 2)[1].Trim()
            break
        }
    }
}

if (-not $RepoDir) {
    $RepoDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot "..\LiminalQAengineer"))
} else {
    $RepoDir = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $RepoDir))
}

if (-not (Test-Path $composeFile)) {
    throw "Missing compose file: $composeFile"
}

$env:LIMINALQA_REPO_DIR = $RepoDir

docker compose --env-file $envFile -f $composeFile down
