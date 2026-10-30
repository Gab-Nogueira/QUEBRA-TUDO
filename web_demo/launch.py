"""Inicia ou reutiliza a demonstração local, mantendo o serviço em segundo plano."""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import webbrowser
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_demo.runtime import identity, state_directory


def health(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
            data = json.load(response)
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def compatible(data, expected, headless):
    return bool(data and data.get("service") == "rastro-demo" and data.get("ok") is True
                and data.get("instance") == expected and data.get("headless") is headless)


def port_available(port):
    try:
        with socket.socket() as listener:
            listener.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5085)
    parser.add_argument("--chrome-visivel", action="store_true")
    parser.add_argument("--abrir", action="store_true", help="Abre o painel no navegador padrão")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("Informe uma porta entre 1 e 65535.")
    expected = identity()
    current = health(args.port)
    if not compatible(current, expected, not args.chrome_visivel):
        if current is not None or not port_available(args.port):
            print(f"A porta {args.port} está ocupada por outra cópia, versão ou configuração do serviço. "
                  "Encerre a instância anterior quando estiver ociosa ou use --port com uma porta livre.")
            return 1
        state_dir = state_directory(args.port, expected["project"])
        state_dir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, "-u", str(Path(__file__).with_name("app.py")), "--port", str(args.port)]
        if args.chrome_visivel:
            command.append("--chrome-visivel")
        with (state_dir / "servidor.log").open("a", encoding="utf-8") as out, (state_dir / "servidor-erros.log").open("a", encoding="utf-8") as err:
            process = subprocess.Popen(command, cwd=str(Path(__file__).parent), stdin=subprocess.DEVNULL,
                                       stdout=out, stderr=err, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1"))
        (state_dir / "servidor.pid").write_text(str(process.pid), encoding="ascii")
        print("Iniciando o Quebra Tudo...", flush=True)
        deadline = time.monotonic() + 60
        while not compatible(health(args.port), expected, not args.chrome_visivel):
            if process.poll() is not None or time.monotonic() > deadline:
                print(f"Não foi possível iniciar. Confira os registros em: {state_dir}")
                return 1
            time.sleep(.6)
    print(f"\nQuebra Tudo disponível: http://localhost:{args.port}")
    for ip in sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}):
        if not ip.startswith(("127.", "169.254.")):
            print(f"Acesso na rede: http://{ip}:{args.port}")
    print("\nAbra o endereço no navegador. O serviço continua ativo em segundo plano.")
    if args.abrir:
        webbrowser.open(f"http://localhost:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
