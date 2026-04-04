$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $repoRoot ".env.liminalqa.local"
$composeFile = Join-Path $repoRoot "deploy/liminalqa-local.compose.yml"

if (-not (Test-Path $composeFile)) {
    throw "Missing compose file: $composeFile"
}

docker compose --env-file $envFile -f $composeFile down -v --remove-orphans
