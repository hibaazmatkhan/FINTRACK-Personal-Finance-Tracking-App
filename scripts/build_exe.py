"""Build standalone FinTrack executable using PyInstaller."""
import sys
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLET_CLIENT_ZIP = ROOT / "scripts" / "flet-windows.zip"
FLET_CLIENT_VERSION = "0.85.3"

# Auto-download the Flet desktop client if not present
if not FLET_CLIENT_ZIP.exists():
    url = f"https://github.com/flet-dev/flet/releases/download/v{FLET_CLIENT_VERSION}/flet-windows.zip"
    print(f"Downloading Flet v{FLET_CLIENT_VERSION} client...")
    urllib.request.urlretrieve(url, str(FLET_CLIENT_ZIP))

# PyInstaller command
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name", "FinTrack",
    "--onedir",
    "--windowed",
    "--noconfirm",
    "--icon", str(ROOT / "app_icon.ico"),
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
    "--paths", str(ROOT / "src"),
    "--add-data", f"{ROOT / 'theme_settings.json'}{';'}.",
    "--add-data", f"{ROOT / '.env'}{';'}.",
    "--add-data", f"{ROOT / 'app_icon.ico'}{';'}.",
    # Bundle the Flet desktop client so end users don't need to download it
    "--add-data", f"{FLET_CLIENT_ZIP}{';'}flet_desktop/app",
    # Hidden imports for Firebase Admin / Supabase / etc.
    "--hidden-import", "firebase_admin",
    "--hidden-import", "supabase",
    "--hidden-import", "dotenv",
    "--hidden-import", "PIL",
    "--hidden-import", "PIL._tkinter_finder",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "requests",
    "--hidden-import", "httpx",
    "--hidden-import", "pyrebase",
    "--hidden-import", "jwt",
    "--hidden-import", "flet",
    "--hidden-import", "flet_desktop",
    "--hidden-import", "flet_charts",
    "--hidden-import", "tkinter",
    "--hidden-import", "asyncio",
    # Collect all sub-packages
    "--collect-submodules", "flet",
    "--collect-submodules", "flet_desktop",
    "--collect-submodules", "flet_charts",
    "--collect-submodules", "services",
    "--collect-submodules", "ui_flet",
    "--collect-submodules", "models",
    str(ROOT / "main_flet.py"),
]

print("Running PyInstaller...")
print(" ".join(str(c) for c in cmd))
result = subprocess.run(cmd, cwd=ROOT)
if result.returncode != 0:
    print(f"PyInstaller failed with return code {result.returncode}")
    sys.exit(1)

print("\nBuild complete! Executable at: dist/FinTrack/FinTrack.exe")
