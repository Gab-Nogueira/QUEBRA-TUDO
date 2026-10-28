"""Prepara os arquivos estáticos e o Chromium headless usados na Vercel."""

from pathlib import Path
import os
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
STATIC_SOURCE = ROOT / "src" / "consulta_assistida" / "web_demo" / "static"
PUBLIC_ROOT = ROOT / "public"
BROWSER_ROOT = ROOT / ".playwright"


def main() -> None:
    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STATIC_SOURCE / "index.html", PUBLIC_ROOT / "index.html")
    static_target = PUBLIC_ROOT / "static"
    static_target.mkdir(parents=True, exist_ok=True)
    for asset in STATIC_SOURCE.iterdir():
        if asset.is_file() and asset.name != "index.html":
            shutil.copy2(asset, static_target / asset.name)

    environment = os.environ.copy()
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSER_ROOT)
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium", "--only-shell"],
        cwd=ROOT,
        env=environment,
        check=True,
    )


if __name__ == "__main__":
    main()
