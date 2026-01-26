#!/bin/bash
set -e

echo "Building Rust core..."
cd rust_core
cargo build --release

# Determine extension based on OS (though we know it's Linux here, good for portability logic)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    EXT="so"
    LIB_PREFIX="lib"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    EXT="dylib"
    LIB_PREFIX="lib"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    EXT="pyd"
    LIB_PREFIX=""
else
    EXT="so"
    LIB_PREFIX="lib"
fi

SOURCE="target/release/${LIB_PREFIX}ghostgpt_core.$EXT"

# Python expects .so for Linux/Mac import
if [[ "$EXT" == "dylib" ]]; then
    DEST="../ghostgpt_core.so"
else
    DEST="../ghostgpt_core.so"
fi

# On windows it might be .dll but python wants .pyd
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    SOURCE="target/release/ghostgpt_core.dll"
    DEST="../ghostgpt_core.pyd"
fi

echo "Copying $SOURCE to $DEST"
cp "$SOURCE" "$DEST"

echo "Build complete."
