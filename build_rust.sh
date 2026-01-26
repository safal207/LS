#!/usr/bin/env bash
# Build script for Rust audio processing module

set -e

echo "=== Building Rust Audio Processing Module ==="

# Navigate to rust_core directory
cd rust_core

# Check if Cargo is installed
if ! command -v cargo &> /dev/null; then
    echo "❌ Cargo not found. Please install Rust:"
    echo "   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

echo "✅ Cargo found"

# Build in release mode for optimal performance
echo "Building in release mode..."
cargo build --release

if [ $? -eq 0 ]; then
    echo "✅ Rust module built successfully!"
    
    # Copy to main directory for easy access
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        cp target/release/libinterview_copilot_core.so ../
        echo "✅ Library copied to main directory"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        cp target/release/libinterview_copilot_core.dylib ../
        echo "✅ Library copied to main directory"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
        cp target/release/interview_copilot_core.dll ../
        echo "✅ Library copied to main directory"
    fi
    
    echo ""
    echo "=== Build Summary ==="
    echo "• Library location: ./target/release/"
    echo "• Ready for Python integration"
    echo "• Memory usage optimized with Rust"
else
    echo "❌ Build failed"
    exit 1
fi