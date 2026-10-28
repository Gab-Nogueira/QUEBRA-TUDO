"""Ponto de entrada Flask para a implantação na Vercel."""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))

# O Chromium vai junto do deploy; o modelo é armazenado apenas no espaço temporário.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".playwright"))
os.environ.setdefault("CYOLA_MODEL_CACHE_DIR", "/tmp/CyolaConsultaAssistida/modelos")

from consulta_assistida.web_demo.app import create_app

app = create_app(
    headless=True,
    synchronous_jobs=True,
    browser="chromium",
    timeout_seconds=270,
    static_directory=ROOT / "public" / "static",
    index_file=ROOT / "public" / "index.html",
)
