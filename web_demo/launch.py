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


def healthy(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            return json.load(response).get("service") == "rastro-demo"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5085)
    parser.add_argument("--chrome-visivel", action="store_true")
    args = parser.parse_args()
    if not healthy(args.port):
        state_dir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CyolaConsultaAssistida" / "web_demo"
        state_dir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-u", str(Path(__file__).with_name("app.py")), "--port", str(args.port)]
        if args.chrome_visivel:
            command.append("--chrome-visivel")
        with (state_dir / "servidor.log").open("a", encoding="utf-8") as out, (state_dir / "servidor-erros.log").open("a", encoding="utf-8") as err:
            process = subprocess.Popen(command, cwd=str(Path(__file__).parent), stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"))
        (state_dir / "servidor.pid").write_text(str(process.pid), encoding="ascii")
        print("Iniciando o Rastro...", flush=True)
        deadline = time.monotonic() + 60
        while not healthy(args.port):
            if process.poll() is not None or time.monotonic() > deadline:
                print(f"Não foi possível iniciar. Confira os registros em: {state_dir}")
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
