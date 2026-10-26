"""Registra imagens do navegador real em etapas da mesma execução."""

from datetime import datetime, timezone
from pathlib import Path


def capturar_etapa(page, pasta: Path, titulo: str):
    try:
        numero = len(list(pasta.glob("frame-*.png"))) + 1
        nome = f"frame-{numero:03d}.png"
        conteudo = page.screenshot(full_page=False, timeout=5000)
        temporario = pasta / f"{nome}.part"
        temporario.write_bytes(conteudo)
        temporario.replace(pasta / nome)
        print(f"CAPTURA: {nome} | {titulo} | {datetime.now(timezone.utc).isoformat()}", flush=True)
        return nome
    except Exception as exc:
        print(f"Captura indisponível nesta etapa: {type(exc).__name__}", flush=True)
        return None
