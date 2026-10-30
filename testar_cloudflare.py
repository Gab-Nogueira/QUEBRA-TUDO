"""Teste real do Turnstile no TJSP, sem consultar processos ou usar resolvedores externos."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from capturas_execucao import capturar_etapa


ROOT = Path(__file__).resolve().parent
URL = "https://eproc-consulta.tjsp.jus.br/consulta_1g/externo_controlador.php?acao=tjsp@consulta_unificada_publica/consultar"
TOKEN_SELECTOR = 'input[name="cf-turnstile-response"]'


def executavel_instalado(navegador: str) -> Path:
    relativo = "Google/Chrome/Application/chrome.exe" if navegador == "chrome" else "Microsoft/Edge/Application/msedge.exe"
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base and (Path(base) / relativo).is_file():
            return Path(base) / relativo
    raise FileNotFoundError(f"Navegador {navegador} não encontrado neste computador.")


@contextmanager
def abrir_pagina(playwright, *, navegador: str, headless: bool, modo_playwright: bool):
    if modo_playwright or navegador == "chromium":
        browser = playwright.chromium.launch(channel=None if navegador == "chromium" else navegador, headless=headless)
        try:
            context = browser.new_context(locale="pt-BR", color_scheme="light", viewport={"width": 1280, "height": 900})
            yield context.new_page()
        finally:
            browser.close()
        return

    # Chrome/Edge instalado, em perfil temporário próprio. A conexão de controle
    # fica somente no loopback; nenhum perfil ou janela existente é reutilizado.
    exe = executavel_instalado(navegador)
    with tempfile.TemporaryDirectory(prefix="quebra-tudo-tjsp-", ignore_cleanup_errors=True) as profile:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        args = [str(exe), f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
                f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
                "--lang=pt-BR", "--window-size=1280,1000"]
        if headless:
            args.append("--headless=new")
        args.append("about:blank")
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        browser = None
        try:
            prazo = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError("O navegador encerrou durante a inicialização.")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= prazo:
                        raise TimeoutError("O navegador não ficou disponível no prazo.")
                    time.sleep(.2)
            browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=15000)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            page.set_viewport_size({"width": 1280, "height": 900})
            yield page
        finally:
            if browser is not None:
                try:
                    browser.new_browser_cdp_session().send("Browser.close")
                except PlaywrightError:
                    pass
                try:
                    browser.close()
                except PlaywrightError:
                    pass
            if process.poll() is None:
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    # Apenas a árvore do processo criado para esta execução.
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    else:
                        process.kill()
                    process.wait(timeout=10)


def liberacao_observada(relato: dict) -> bool:
    """Apenas a etapa do widget; nunca equivale à aceitação de uma consulta."""
    return (
        relato.get("resultado") == "widget_liberado_sem_consulta"
        and all(relato.get(key) is True for key in (
            "formulario_carregado", "widget_detectado", "resposta_emitida",
            "liberacao_automatica_observada",
        ))
        and relato.get("intervencao_humana") is False
    )


def mensagem_resultado(relato: dict) -> str:
    if liberacao_observada(relato):
        return "O Cloudflare emitiu a resposta nesta tentativa automática. A consulta de processo e a aceitação pelo TJSP ainda não foram testadas."
    mensagens = {
        "nao_liberou_no_prazo": "O Cloudflare não liberou o desafio no prazo desta tentativa. O funcionamento automático não foi comprovado.",
        "widget_nao_encontrado": "O formulário abriu, mas o widget do Cloudflare não foi identificado.",
        "formulario_nao_encontrado": "O formulário público do TJSP não foi identificado nesta tentativa.",
        "pagina_indisponivel": "O TJSP respondeu com um erro HTTP. Não foi possível testar o desafio.",
        "interrompido": "O teste foi interrompido antes da conclusão.",
        "erro_tecnico": "Um erro técnico impediu a conclusão do teste. Confira o diagnóstico desta tentativa.",
    }
    return mensagens.get(relato.get("resultado"), "A liberação do Cloudflare não foi confirmada nesta tentativa.")


def frames_cloudflare(page):
    return [frame for frame in page.frames if urlparse(frame.url).hostname == "challenges.cloudflare.com"]


def ler_estado(page) -> dict:
    # Retorna somente booleanos: o valor do token não sai do navegador.
    return {
        "formulario_carregado": page.locator("#txtNumProcesso").is_visible()
        and page.locator("#selInstancia").is_visible(),
        "widget_detectado": bool(page.locator(TOKEN_SELECTOR).count() or frames_cloudflare(page)),
        "resposta_emitida": page.locator(TOKEN_SELECTOR).evaluate_all(
            "els => els.some(e => Boolean(e.value.trim()))"
        ),
    }


def checkbox_nodes(node):
    """Localiza caixas reais, inclusive no shadow DOM fechado do widget."""
    attrs = dict(zip(node.get("attributes", [])[::2], node.get("attributes", [])[1::2]))
    if node.get("nodeName") == "INPUT" and attrs.get("type") == "checkbox" and "disabled" not in attrs:
        yield node["nodeId"]
    for child in node.get("children", []) + node.get("shadowRoots", []):
        yield from checkbox_nodes(child)


def acionar_caixa(page, frame) -> str | None:
    """Uma interação normal na caixa visível, sem alterar o widget ou seus tokens."""
    caixa = frame.get_by_role("checkbox")
    if caixa.count() == 1 and caixa.is_visible() and caixa.is_enabled():
        caixa.click(timeout=1500)
        return "clique_na_caixa"
    # O Turnstile pode encapsular a caixa em shadow DOM fechado. O protocolo
    # do próprio Chrome permite focar o elemento real e acioná-lo com Espaço.
    # Não se injeta resposta, callback, chave de teste ou evento JavaScript.
    session = page.context.new_cdp_session(frame)
    try:
        document = session.send("DOM.getDocument", {"depth": -1, "pierce": True})
        for node_id in checkbox_nodes(document["root"]):
            try:
                box = session.send("DOM.getBoxModel", {"nodeId": node_id})["model"]
            except PlaywrightError:
                continue  # Elementos sem layout não são alvos de interação.
            if box["width"] <= 0 or box["height"] <= 0:
                continue
            session.send("DOM.focus", {"nodeId": node_id})
            page.keyboard.press("Space")
            return "espaco_na_caixa_focada"
    finally:
        session.detach()
    return None


def testar_pagina(page, relato: dict, *, espera: int, etapa) -> int:
    print("TJSP: abrindo a consulta pública, sem número de processo...", flush=True)
    resposta = page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    relato["http_status"] = resposta.status if resposta else None
    if resposta and not resposta.ok:
        relato["resultado"] = "pagina_indisponivel"
        etapa("TJSP indisponível nesta tentativa")
        return 2
    etapa("Página pública do TJSP carregada")
    print("TJSP: aguardando a verificação do Cloudflare...", flush=True)
    prazo = time.monotonic() + espera
    proxima_interacao = time.monotonic() + 3
    while time.monotonic() < prazo:
        relato.update(ler_estado(page))
        if relato["formulario_carregado"] and relato["widget_detectado"] and relato["resposta_emitida"]:
            relato.update(resultado="widget_liberado_sem_consulta", liberacao_automatica_observada=True)
            print("TJSP: resposta emitida pelo Cloudflare; consulta processual não realizada.", flush=True)
            page.wait_for_timeout(800)
            etapa("Resposta da verificação recebida; consulta processual não realizada")
            return 0
        if not relato["interacao_automatica"] and time.monotonic() >= proxima_interacao:
            for frame in frames_cloudflare(page):
                try:
                    metodo = acionar_caixa(page, frame)
                except PlaywrightError:
                    # O iframe pode ser substituído durante a verificação.
                    metodo = None
                if metodo:
                    relato.update(interacao_automatica=True, metodo_interacao=metodo)
                    print("TJSP: acionando a caixa de verificação uma única vez...", flush=True)
                    etapa("Caixa do Cloudflare acionada automaticamente")
                    break
            proxima_interacao = time.monotonic() + 2
        page.wait_for_timeout(500)
    relato["resultado"] = (
        "formulario_nao_encontrado" if not relato["formulario_carregado"] else
        "widget_nao_encontrado" if not relato["widget_detectado"] else "nao_liberou_no_prazo"
    )
    etapa("Fim do teste: liberação não confirmada")
    return 1


def tempo_espera(valor: str) -> int:
    numero = int(valor)
    if not 5 <= numero <= 120:
        raise argparse.ArgumentTypeError("Informe uma espera entre 5 e 120 segundos.")
    return numero


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true", help="Executa sem janela; o resultado pode diferir do navegador visível")
    parser.add_argument("--modo-playwright", action="store_true", help="Diagnóstico: usa a inicialização padrão do Playwright em vez do navegador instalado")
    parser.add_argument("--espera", type=tempo_espera, default=60, help="Tempo máximo de espera pelo widget, em segundos (5 a 120)")
    args = parser.parse_args(argv)
    pasta = ROOT / "evidencias_cloudflare" / uuid4().hex[:12]
    pasta.mkdir(parents=True, exist_ok=False)
    print(f"Evidências: {pasta}", flush=True)
    relato = {
        "url": URL, "data_hora_utc": datetime.now(timezone.utc).isoformat(),
        "navegador": args.navegador, "headless": args.headless,
        "inicializacao": "playwright" if args.modo_playwright or args.navegador == "chromium" else "navegador_instalado_perfil_temporario",
        "escopo": "somente_widget_sem_consulta", "resultado": "inconclusivo",
        "formulario_carregado": False, "widget_detectado": False, "resposta_emitida": False,
        "interacao_automatica": False, "metodo_interacao": None,
        "liberacao_automatica_observada": False, "intervencao_humana": False,
        "consulta_realizada": False, "validacao_servidor_confirmada": False,
        "servico_externo_de_resolucao": False, "espera_maxima_segundos": args.espera,
    }
    codigo = 2
    inicio = time.monotonic()
    try:
        with sync_playwright() as playwright:
            with abrir_pagina(playwright, navegador=args.navegador, headless=args.headless, modo_playwright=args.modo_playwright) as page:
                page.set_default_timeout(5000)
                try:
                    codigo = testar_pagina(page, relato, espera=args.espera,
                                           etapa=lambda titulo: capturar_etapa(page, pasta, titulo))
                finally:
                    if not page.is_closed():
                        try:
                            page.screenshot(path=str(pasta / "tela.png"), timeout=5000)
                        except PlaywrightError:
                            pass
    except KeyboardInterrupt:
        relato["resultado"] = "interrompido"
        codigo = 2
    except Exception as exc:
        relato.update(resultado="erro_tecnico", erro_tipo=type(exc).__name__)
        codigo = 2
        # Não incluir dumps de página, URLs internas do desafio ou tokens em logs.
        print(f"Diagnóstico: {type(exc).__name__}. Verifique conexão, navegador e dependências.", flush=True)
    relato["duracao_segundos"] = round(time.monotonic() - inicio, 2)
    relato["mensagem"] = mensagem_resultado(relato)
    (pasta / "resultado.json").write_text(json.dumps(relato, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relato, ensure_ascii=False, indent=2), flush=True)
    print("\n" + relato["mensagem"], flush=True)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
