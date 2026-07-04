"""Build standalone FinTrack executable using PyInstaller."""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# PyInstaller command
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name", "FinTrack",
    "--onedir",
    "--windowed",
    "--icon", str(ROOT / "app_icon.ico"),
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
    "--paths", str(ROOT / "src"),
    "--add-data", f"{ROOT / 'theme_settings.json'}{';'}.",
    "--add-data", f"{ROOT / '.env'}{';'}.",
    "--add-data", f"{ROOT / 'app_icon.ico'}{';'}.",
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
