"""Identifica a cópia e a revisão carregadas pelo serviço local."""

import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def identity(root=ROOT):
    root = Path(root).resolve()
    project = hashlib.sha256(os.path.normcase(str(root)).encode("utf-8")).hexdigest()[:16]
    digest = hashlib.sha256()
    files = list(root.glob("*.py")) + list((root / "web_demo").glob("*.py"))
    files += list((root / "web_demo" / "static").glob("*"))
    for file in sorted(path for path in files if path.is_file()):
        digest.update(file.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(file.read_bytes())
    return {"project": project, "revision": digest.hexdigest()[:16]}


def state_directory(port, project):
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CyolaConsultaAssistida"
    return base / f"web_demo_{project}_{port}"
