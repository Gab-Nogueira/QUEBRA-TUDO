"""Demonstração interna do Rastro, com execução local dos testes existentes."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from io import StringIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
from urllib.parse import urlparse
from uuid import uuid4

from flask import Flask, Response, abort, jsonify, request, send_file

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rastreamento_correios import normalizar_objeto

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
    def __init__(self, state_dir: Path, *, headless=True):
        self.state_dir = state_dir
        state_dir.mkdir(parents=True, exist_ok=True)
        self.file = state_dir / "execucoes.json"
        self.lock = threading.RLock()
        self.active = None
        self.headless = headless
        try:
            self.items = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.items = {}
        for item in self.items.values():
            if item["status"] == "executando":
                item.update(status="falhou", message="A demonstração foi reiniciada antes de concluir este teste.", phase="Execução interrompida")

    def save(self):
        temp = self.file.with_suffix(".tmp")
        temp.write_text(json.dumps(self.items, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.file)

    def public(self, item):
        return {key: value for key, value in item.items() if not key.startswith("_")}

    def recent(self):
        with self.lock:
            return [self.public(job) for job in sorted(self.items.values(), key=lambda item: item["created_at"], reverse=True)[:15]]

    def start(self, kind, code):
        with self.lock:
            if self.active:
                return None
            ident = uuid4().hex
            job = {"id": ident, "kind": kind, "title": KINDS[kind], "code": code, "example": code == EXAMPLE,
                   "created_at": utc_now(), "status": "executando", "progress": 5, "phase": "Preparando a consulta",
                   "message": "O teste está começando.", "result": None, "frames": []}
            self.items[ident] = job
            self.active = ident
            self.save()
            threading.Thread(target=self.run, args=(ident,), daemon=True, name=f"rastro-{ident[:8]}").start()
            return self.public(job)

    def run(self, ident):
        job = self.items[ident]
        if job["kind"] == "recaptcha":
            args = [sys.executable, "-u", str(ROOT / "testar_recaptcha.py"), "--automatico", "--navegador", "chrome"]
        else:
            args = [sys.executable, "-u", str(ROOT / "rastreamento_correios.py"), "--navegador", "chrome", "--sem-copiar"]
            if job["code"]:
                args += ["--objeto", job["code"]]
        if self.headless:
            args.append("--headless")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        evidence = None
        lines = []
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

            timer = threading.Timer(300, expire)
            timer.daemon = True
            timer.start()
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                lines.append(line)
                if line.startswith("CAPTCHA RECONHECIDO: "):
                    with self.lock:
                        job["recognized_text"] = line.removeprefix("CAPTCHA RECONHECIDO: ")
                if line.startswith("Evidências: "):
                    evidence = Path(line.partition(": ")[2]).resolve()
                    roots = ((ROOT / "evidencias_correios").resolve(), (ROOT / "evidencias_recaptcha").resolve())
                    if any(evidence.is_relative_to(root) for root in roots):
                        with self.lock:
                            job["_evidence"] = str(evidence)
                if line.startswith("CAPTURA: "):
                    parts = line.removeprefix("CAPTURA: ").split(" | ", 2)
                    if len(parts) == 3 and re.fullmatch(r"frame-\d{3}\.png", parts[0]):
                        with self.lock:
                            job["frames"].append({"name": parts[0], "title": parts[1], "created_at": parts[2]})
                with self.lock:
                    for marker, progress, phase in (
                        ("Carregando", 12, "Preparando o reconhecimento local"),
                        ("Reconhecimento local pronto", 25, "Abrindo o site de origem"),
                        ("Clicando uma vez", 35, "Iniciando a verificação"),
                        ("desafio de áudio", 48, "Reconhecendo o desafio"),
                        ("CAPTCHA RECONHECIDO:", 68, "Texto reconhecido, conferindo o resultado"),
                        ("transcrição local concluída", 75, "Enviando a resposta para validação"),
                        ("RASTREAMENTO DO OBJETO", 90, "Organizando os dados da encomenda"),
                    ):
                        if marker in line and progress >= job["progress"]:
                            job.update(progress=progress, phase=phase)
            process.wait()
            timer.cancel()
            if timed_out.is_set():
                raise RuntimeError("O site demorou mais que o esperado. Esta tentativa foi encerrada; você pode tentar novamente.")
            roots = ((ROOT / "evidencias_correios").resolve(), (ROOT / "evidencias_recaptcha").resolve())
            if evidence is None or not any(evidence.is_relative_to(root) for root in roots):
                raise RuntimeError("Não foi possível obter o retorno desta execução.")
            report = json.loads((evidence / "resultado.json").read_text(encoding="utf-8"))
            ok, message = classify_report(job["kind"], report, job["code"])
            with self.lock:
                job.update(status="concluido" if ok else "falhou", progress=100,
                           phase="Leitura concluída" if ok and job["kind"] == "letras" else "Consulta concluída" if ok else "Tentativa encerrada",
                           message=message, result=report, _evidence=str(evidence))
        except Exception as exc:
            with self.lock:
                job.update(status="falhou", progress=100, phase="Tentativa encerrada", message=str(exc))
        finally:
            if timer:
                timer.cancel()
            with self.lock:
                job["finished_at"] = utc_now()
                job["_log"] = lines[-150:]
                self.active = None
                self.save()

    def artifact(self, ident, name):
        job = self.items.get(ident)
        if not job or not job.get("_evidence"):
            return None
        evidence = Path(job["_evidence"]).resolve()
        allowed = ((ROOT / "evidencias_correios").resolve(), (ROOT / "evidencias_recaptcha").resolve())
        if not any(evidence.is_relative_to(base) for base in allowed):
            return None
        if name == "captcha.png":
            images = sorted(evidence.glob("captcha-*.png"))
            return images[-1] if images else None
        if name == "audio.mp3":
            audios = sorted(evidence.glob("audio-*.mp3"))
            return audios[-1] if audios else None
        if re.fullmatch(r"frame-\d{3}\.png", name):
            path = evidence / name
            return path if path.is_file() else None
        if name in {"tela.png", "resultado.json"}:
            path = evidence / name
            return path if path.is_file() else None
        return None


def get_proofs():
    proofs = {}
    for folder, kind in (("evidencias_correios", "rastreamento"), ("evidencias_recaptcha", "recaptcha")):
        for file in (ROOT / folder).glob("*/resultado.json"):
            try:
                report = json.loads(file.read_text(encoding="utf-8"))
                if kind == "rastreamento" and report.get("codigo_consultado") != EXAMPLE:
                    continue
                ok, _ = classify_report(kind, report, EXAMPLE)
                if not ok:
                    continue
                date = report.get("data_hora_utc", "")
                if kind not in proofs or date > proofs[kind]["date"]:
                    proofs[kind] = {"kind": kind, "date": date, "confirmed": True, "report": report,
                                    "_path": str(file.parent)}
            except (OSError, ValueError):
                continue
    return proofs


def csv_text(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def create_app(*, state_dir=None, headless=True):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.update(MAX_CONTENT_LENGTH=8192)
    state_dir = Path(state_dir) if state_dir else Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CyolaConsultaAssistida" / "web_demo"
    jobs = Jobs(state_dir, headless=headless)
    app.extensions["jobs"] = jobs
    proofs = get_proofs()

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
        return app.send_static_file("index.html")

    @app.get("/api/health")
    def health():
        return {"ok": True, "service": "rastro-demo", "active": jobs.active}

    @app.get("/api/bootstrap")
    def bootstrap():
        return {"active": jobs.active, "jobs": jobs.recent(), "example": EXAMPLE,
                "proofs": [{key: value for key, value in item.items() if not key.startswith("_")} for item in proofs.values()]}

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
        return job, 202

    @app.get("/api/jobs/<ident>")
    def get_job(ident):
        with jobs.lock:
            item = jobs.items.get(ident)
            if item is None:
                abort(404)
            return jobs.public(item)

    @app.get("/api/jobs/<ident>/artifacts/<name>")
    def artifact(ident, name):
        path = jobs.artifact(ident, name)
        if path is None:
            abort(404)
        return send_file(path, as_attachment=name.endswith(".json"), download_name="relatorio-execucao.json" if name.endswith(".json") else name)

    @app.get("/api/proofs/<kind>/tela.png")
    def proof_image(kind):
        proof = proofs.get(kind)
        if not proof:
            abort(404)
        return send_file(Path(proof["_path"]) / "tela.png")

    @app.get("/api/jobs/<ident>/report.csv")
    def report_csv(ident):
        job = jobs.items.get(ident)
        if not job or job["kind"] != "rastreamento" or job["status"] != "concluido":
            abort(404)
        report = job["result"]["rastreamento"]
        output = StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        keys = ("codigo", "situacao", "ultimo_local_informado", "em_transito_para", "ultima_atualizacao", "previsao_entrega", "observacao_previsao")
        writer.writerow(("Código", "Situação", "Último local informado", "Em trânsito para", "Última atualização", "Previsão dos Correios", "Observação"))
        writer.writerow(csv_text(report.get(key)) for key in keys)
        return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="rastreamento.csv"'})

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
