"""Inicia ou reutiliza a demonstração local, mantendo o serviço em segundo plano."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "src"


def healthy(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return json.load(response).get("service") == "consulta-assistida-sem-retencao"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5085)
    parser.add_argument("--chrome-visivel", action="store_true")
    args = parser.parse_args()
    if not healthy(args.port):
        pythonpath = os.environ.get("PYTHONPATH", "")
        if str(SOURCE_ROOT) not in pythonpath.split(os.pathsep):
            pythonpath = str(SOURCE_ROOT) + (os.pathsep + pythonpath if pythonpath else "")
        environment = dict(os.environ, PYTHONPATH=pythonpath, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        command = [sys.executable, "-u", "-m", "consulta_assistida.web_demo.app", "--port", str(args.port)]
        if args.chrome_visivel:
            command.append("--chrome-visivel")
        process = subprocess.Popen(command, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=environment)
        print("Iniciando o Rastro...", flush=True)
        deadline = time.monotonic() + 60
        while not healthy(args.port):
            if process.poll() is not None or time.monotonic() > deadline:
                print("Nao foi possivel iniciar. Confira as dependencias e a porta configurada.")
                return 1
            time.sleep(.6)
    print(f"\nRastro disponível: http://localhost:{args.port}")
    for ip in sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}):
        if not ip.startswith(("127.", "169.254.")):
            print(f"Acesso na rede: http://{ip}:{args.port}")
    print("\nAbra o endereço no navegador. O serviço continua ativo em segundo plano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
