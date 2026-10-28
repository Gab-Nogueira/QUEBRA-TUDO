"""Demonstração interna do Rastro, com execução local dos testes existentes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.parse import urlparse
from uuid import uuid4

from flask import Flask, abort, request, send_file

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "src"
sys.path.insert(0, str(SOURCE_ROOT))
from consulta_assistida.rastreamento_correios import normalizar_objeto

KINDS = {"rastreamento": "Rastreamento dos Correios", "letras": "Leitura de letras", "recaptcha": "Verificação reCAPTCHA"}
EXAMPLE = "AA123456785BR"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def classify_report(kind: str, report: dict, code: str = "") -> tuple[bool, str]:
    if kind == "rastreamento":
        ok = bool(report.get("consulta_confirmada") and report.get("captcha_validado_pelo_servidor")
                  and report.get("rastreamento", {}).get("codigo") == code)
        return ok, "Consulta confirmada pelos Correios" if ok else str(report.get("erro") or report.get("mensagem_correios") or "Os Correios não confirmaram esta consulta. Você pode tentar novamente.")
    if kind == "letras":
        ok = report.get("resultado") == "leitura_realizada_sem_consulta" and bool(report.get("tentativas"))
        return ok, "Texto reconhecido na imagem" if ok else str(report.get("erro") or "Não foi possível ler a imagem nesta tentativa.")
    ok = bool(report.get("validacao_servidor_confirmada"))
    return ok, "Verificação confirmada pelo Google" if ok else str(report.get("erro") or "O Google não confirmou a verificação nesta tentativa.")


class Jobs:
    def __init__(self, *, headless=True, synchronous=False, browser="chrome", timeout_seconds=300):
        self.lock = threading.RLock()
        self.active = None
        self.headless = headless
        self.synchronous = synchronous
        self.browser = browser
        self.timeout_seconds = timeout_seconds
        self.items = {}

    def public(self, item):
        return {key: value for key, value in item.items() if not key.startswith("_")}

    def start(self, kind, code):
        with self.lock:
            if self.active:
                return None
            self.items.clear()
            ident = uuid4().hex
            job = {"id": ident, "kind": kind, "title": KINDS[kind], "code": code, "example": code == EXAMPLE,
                   "created_at": utc_now(), "status": "executando", "progress": 5, "phase": "Preparando a consulta",
                   "message": "O teste está começando.", "result": None}
            self.items[ident] = job
            self.active = ident
            if self.synchronous:
                self.run(ident)
                return self.public(job)
            threading.Thread(target=self.run, args=(ident,), daemon=True, name=f"rastro-{ident[:8]}").start()
            return self.public(job)

    def run(self, ident):
        job = self.items[ident]
        if job["kind"] == "recaptcha":
            args = [sys.executable, "-u", "-m", "consulta_assistida.testar_recaptcha", "--automatico", "--navegador", self.browser, "--json-stdout"]
        else:
            args = [sys.executable, "-u", "-m", "consulta_assistida.rastreamento_correios", "--navegador", self.browser, "--sem-copiar", "--json-stdout"]
            if job["code"]:
                args += ["--objeto", job["code"]]
        if self.headless:
            args.append("--headless")
        pythonpath = os.environ.get("PYTHONPATH", "")
        if str(SOURCE_ROOT) not in pythonpath.split(os.pathsep):
            pythonpath = str(SOURCE_ROOT) + (os.pathsep + pythonpath if pythonpath else "")
        env = dict(os.environ, PYTHONPATH=pythonpath, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        timer = None
        timed_out = threading.Event()
        try:
            process = subprocess.Popen(args, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

            def expire():
                timed_out.set()
                if process.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    else:
                        process.kill()

            timer = threading.Timer(self.timeout_seconds, expire)
            timer.daemon = True
            timer.start()
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("RELATORIO_JSON:"):
                    try:
                        with self.lock:
                            job["_report"] = json.loads(line.removeprefix("RELATORIO_JSON:"))
                    except ValueError:
                        pass
                if line.startswith("CAPTCHA RECONHECIDO: "):
                    with self.lock:
                        job["recognized_text"] = line.removeprefix("CAPTCHA RECONHECIDO: ")
                with self.lock:
                    for marker, progress, phase in (
                        ("Carregando", 12, "Preparando o reconhecimento local"),
                        ("Reconhecimento local pronto", 25, "Abrindo o site de origem"),
                        ("Clicando uma vez", 35, "Iniciando a verificacao"),
                        ("desafio de audio", 48, "Reconhecendo o desafio"),
                        ("CAPTCHA RECONHECIDO:", 68, "Texto reconhecido, conferindo o resultado"),
                        ("transcricao local concluida", 75, "Enviando a resposta para validacao"),
                        ("RASTREAMENTO DO OBJETO", 90, "Organizando os dados da encomenda"),
                    ):
                        if marker in line and progress >= job["progress"]:
                            job.update(progress=progress, phase=phase)
            process.wait()
            timer.cancel()
            if timed_out.is_set():
                raise RuntimeError("O site demorou mais que o esperado. Esta tentativa foi encerrada.")
            report = job.get("_report")
            if not isinstance(report, dict):
                raise RuntimeError("Nao foi possivel obter o resultado desta execucao.")
            ok, message = classify_report(job["kind"], report, job["code"])
            with self.lock:
                job.update(status="concluido" if ok else "falhou", progress=100,
                           phase="Consulta concluida" if ok else "Tentativa encerrada",
                           message=message, result=report)
        except Exception as exc:
            with self.lock:
                job.update(status="falhou", progress=100, phase="Tentativa encerrada", message=str(exc))
        finally:
            if timer:
                timer.cancel()
            with self.lock:
                job["finished_at"] = utc_now()
                self.active = None

def create_app(*, headless=True, synchronous_jobs=False, browser="chrome", timeout_seconds=300,
               static_directory=None, index_file=None):
    static_folder = str(static_directory) if static_directory else "static"
    app = Flask(__name__, static_folder=static_folder, static_url_path="/static")
    app.config.update(MAX_CONTENT_LENGTH=8192)
    jobs = Jobs(headless=headless, synchronous=synchronous_jobs, browser=browser,
                timeout_seconds=timeout_seconds)
    app.extensions["jobs"] = jobs

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        if index_file:
            return send_file(index_file)
        return app.send_static_file("index.html")

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "consulta-assistida-sem-retencao", "active": jobs.active}

    @app.post("/api/jobs")
    def start_job():
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return {"error": "Abra a ferramenta neste endereço para iniciar uma consulta."}, 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get("kind") not in KINDS:
            return {"error": "Escolha uma das três opções de consulta."}, 400
        kind = data["kind"]
        code = data.get("code", "")
        if not isinstance(code, str):
            return {"error": "Informe um código de rastreamento válido."}, 400
        try:
            code = normalizar_objeto(code) if kind == "rastreamento" else ""
            if kind == "rastreamento" and not code:
                raise ValueError("Informe o código da encomenda ou use o código de exemplo.")
        except ValueError as exc:
            return {"error": str(exc)}, 400
        job = jobs.start(kind, code)
        if job is None:
            return {"error": "Já há uma consulta em andamento. Aguarde a conclusão.", "active": jobs.active}, 409
        return job, 200 if jobs.synchronous else 202

    @app.get("/api/jobs/<ident>")
    def get_job(ident):
        with jobs.lock:
            item = jobs.items.get(ident)
            if item is None:
                abort(404)
            return jobs.public(item)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5085)
    parser.add_argument("--chrome-visivel", action="store_true")
    args = parser.parse_args()
    from waitress import serve
    print(f"Rastro: http://localhost:{args.port}", flush=True)
    serve(create_app(headless=not args.chrome_visivel), host=args.host, port=args.port, threads=6)
