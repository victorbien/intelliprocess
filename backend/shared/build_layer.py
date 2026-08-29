"""Build script to sync app/ modules into the shared Lambda layer.

Usage:
    python shared/build_layer.py

This copies the relevant app/ source files into shared/python/app/
so SAM can package them into the Lambda Layer. Run this before `sam build`.

On CI/CD, call this as a pre-build step.
"""

import shutil
from pathlib import Path

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
APP_DIR = BACKEND_DIR / "app"
LAYER_APP_DIR = SCRIPT_DIR / "python" / "app"


def sync_layer() -> None:
    """Copy app source modules into the layer package directory."""
    # Ensure the target app/ directory exists
    LAYER_APP_DIR.mkdir(parents=True, exist_ok=True)

    # Modules to include in the layer
    modules_to_copy = [
        "config.py",
        "__init__.py",
        "models",
        "services",
        "middleware",
    ]

    for module in modules_to_copy:
        src = APP_DIR / module
        dst = LAYER_APP_DIR / module

        if not src.exists():
            print(f"  [SKIP] {module} — source not found")
            continue

        # Remove existing destination
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()

        # Copy
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            print(f"  [DIR]  {module}/")
        else:
            shutil.copy2(src, dst)
            print(f"  [FILE] {module}")

    print(f"\nLayer sync complete → {LAYER_APP_DIR}")


if __name__ == "__main__":
    print("Syncing app/ modules into shared layer...\n")
    sync_layer()
