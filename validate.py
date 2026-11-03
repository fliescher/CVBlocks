
import sys
import subprocess
import venv
from pathlib import Path

# Project root directory
ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"

# Platform-independent paths to virtual environment executables
if sys.platform == "win32":
    PYTHON = VENV_DIR / "Scripts" / "python.exe"
    PIP = VENV_DIR / "Scripts" / "pip.exe"
else:
    PYTHON = VENV_DIR / "bin" / "python"
    PIP = VENV_DIR / "bin" / "pip"


def run(*args):
    """Run a command and stop if it fails."""
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    # Create virtual environment if it doesn't exist
    if not VENV_DIR.exists():
        print("Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)

    # Validate dataset
    print("Validating dataset...")
    run(str(PYTHON), "src/render.py", "--check")

if __name__ == "__main__":
    main()
