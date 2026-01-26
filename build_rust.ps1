# Build script for Rust audio processing module (Windows)

Write-Host "=== Building Rust Audio Processing Module ===" -ForegroundColor Green

# Navigate to rust_core directory
Set-Location rust_core

# Check if Cargo is installed
$cargoExists = Get-Command cargo -ErrorAction SilentlyContinue
if (-not $cargoExists) {
    Write-Host "❌ Cargo not found. Please install Rust:" -ForegroundColor Red
    Write-Host "   Download from: https://www.rust-lang.org/tools/install" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Cargo found" -ForegroundColor Green

# Build in release mode for optimal performance
Write-Host "Building in release mode..." -ForegroundColor Cyan
cargo build --release

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Rust module built successfully!" -ForegroundColor Green
    
    # Copy to main directory for easy access
    Copy-Item "target\release\interview_copilot_core.dll" "..\"
    Write-Host "✅ Library copied to main directory" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "=== Build Summary ===" -ForegroundColor Blue
    Write-Host "• Library location: .\target\release\" -ForegroundColor White
    Write-Host "• Ready for Python integration" -ForegroundColor White
    Write-Host "• Memory usage optimized with Rust" -ForegroundColor White
} else {
    Write-Host "❌ Build failed" -ForegroundColor Red
    exit 1
}