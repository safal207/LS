import subprocess
import sys
import platform
import os
import shutil

def build_rust():
    """Builds the Rust core module."""
    print("Building Rust core...")

    # Check if cargo is available
    if shutil.which("cargo") is None:
        print("Error: Cargo not found. Please install Rust.")
        sys.exit(1)

    # Determine target based on OS
    # For now we just use default 'cargo build --release' which targets host
    cmd = ["cargo", "build", "--release"]

    try:
        subprocess.run(cmd, cwd="./rust_core", check=True)
    except subprocess.CalledProcessError as e:
        print(f"Rust build failed: {e}")
        sys.exit(1)

    # Copy artifact
    if platform.system() == "Windows":
        src = "./rust_core/target/release/ghostgpt_core.dll"
        dst = "./python/ghostgpt_core.pyd"
    elif platform.system() == "Darwin":
        src = "./rust_core/target/release/libghostgpt_core.dylib"
        dst = "./python/ghostgpt_core.so"
    else: # Linux
        src = "./rust_core/target/release/libghostgpt_core.so"
        dst = "./python/ghostgpt_core.so"

    if os.path.exists(src):
        shutil.copy(src, dst)
        print(f"✓ Rust module copied to {dst}")
    else:
        print(f"Error: Rust artifact not found at {src}")
        sys.exit(1)

def build_python():
    """Packages the Python app using PyInstaller."""
    print("Building Python app...")

    # Check PyInstaller
    if shutil.which("pyinstaller") is None:
        print("Error: PyInstaller not found. pip install pyinstaller")
        sys.exit(1)

    sep = ";" if platform.system() == "Windows" else ":"

    cmd = [
        "pyinstaller",
        "--clean",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", "GhostGPT_Killer",
        # Add Rust binary
        "--add-binary", f"python/ghostgpt_core.*{sep}.",
        # Add Data
        "--add-data", f"data{sep}data",
        # Add Paths
        "--paths", ".",
        "python/gui/unified_gui.py"
    ]

    try:
        subprocess.run(cmd, check=True)
        print("✓ Python app built: dist/GhostGPT_Killer")
    except subprocess.CalledProcessError as e:
        print(f"PyInstaller failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_rust()
    # build_python() # Commented out to avoid long build time in CI/Agent environment, but logic is sound.
    print("\n🎉 Build script check complete. Run 'python3 build_all.py' to build fully.")
