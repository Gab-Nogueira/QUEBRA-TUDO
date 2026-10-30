"""Consulta pública por número CNJ, com captura e confirmação da página do processo."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlparse
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright
from capturas_execucao import capturar_etapa
from testar_cloudflare import URL, TOKEN_SELECTOR, abrir_pagina

ROOT = Path(__file__).resolve().parent
HOSTS = {"eproc-consulta.tjsp.jus.br", "eproc2g-consulta.tjsp.jus.br", "esaj.tjsp.jus.br"}


def normalizar_processo(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"(?:[0-9]{20}|[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4})", value):
        raise ValueError("Informe o número completo do processo: 20 dígitos, com ou sem pontuação.")
    digits = re.sub(r"\D", "", value)
    if digits[13:16] != "826":
        raise ValueError("Este campo consulta o TJSP. Confira se o número contém .8.26.")
    return f"{digits[:7]}-{digits[7:9]}.{digits[9:13]}.{digits[13]}.{digits[14:16]}.{digits[16:]}"


def digitos_conferem(numero: str) -> bool:
    digits = re.sub(r"\D", "", numero)
    return len(digits) == 20 and int(digits[:7] + digits[9:] + digits[7:9]) % 97 == 1


def oficial(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in HOSTS


def texto_simples(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def detalhes_correspondem(url: str, text: str, numero: str, formulario: bool) -> bool:
    """Não aceita número no input, URL, lista ou mensagem de erro como prova."""
    if not oficial(url) or formulario:
        return False
    texto = texto_simples(text)
    if any(x in texto for x in ("processo nao encontrado", "numero invalido", "nenhum processo encontrado", "acesso negado", "verifique se voce e humano")):
        return False
    numeros = re.findall(r"(?<!\d)(?:\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}|\d{20})(?!\d)", text)
    igual = any(re.sub(r"\D", "", n) == re.sub(r"\D", "", numero) for n in numeros)
    # Seções de detalhes, tanto do eproc quanto do e-SAJ; menus isolados não bastam.
    partes = "partes do processo" in texto or "partes e representantes" in texto
    movimentos = "movimentacoes" in texto or "eventos do processo" in texto
    return igual and partes and movimentos and ("classe" in texto or "assunto" in texto)


def consulta_confirmada(report: dict, code: str = "") -> bool:
    try:
        numero = normalizar_processo(code or report.get("numero_consultado", ""))
    except (ValueError, AttributeError):
        return False
    return (digitos_conferem(numero) and report.get("resultado") == "processo_aberto"
            and report.get("numero_consultado") == numero
            and report.get("numero_confirmado") == numero
            and all(report.get(k) is True for k in ("consulta_enviada", "pagina_processo_confirmada", "validacao_servidor_confirmada"))
            and report.get("captura_estavel") is True
            and oficial(report.get("url_final", ""))
            and bool(re.fullmatch(r"frame-\d{3}\.png", report.get("captura_resultado") or "")))


def resposta_confirmada(report: dict, code: str = "") -> bool:
    if consulta_confirmada(report, code):
        return True
    return (report.get("resultado") == "retorno_sem_processo"
            and bool(code) and report.get("numero_consultado") == code
            and report.get("consulta_enviada") is True
            and report.get("pagina_seguinte_observada") is True
            and report.get("resposta_consulta_recebida") is True
            and report.get("captura_estavel") is True
            and report.get("mensagem_portal") in {"Número inválido", "Processo não encontrado", "Página de retorno do TJSP", "Não existem informações disponíveis para os parâmetros informados"}
            and isinstance(report.get("http_status_consulta"), int)
            and 200 <= report["http_status_consulta"] < 300
            and oficial(report.get("url_final", ""))
            and bool(re.fullmatch(r"frame-\d{3}\.png", report.get("captura_resultado") or "")))


def mensagem_resultado(report: dict) -> str:
    if consulta_confirmada(report):
        return "O TJSP abriu a página de detalhes do processo informado. A captura registra o resultado após a consulta."
    if resposta_confirmada(report, report.get("numero_consultado", "")):
        return f"O TJSP respondeu à consulta: {report['mensagem_portal'].lower()}. A tela de retorno foi registrada; nenhum processo foi confirmado."
    return {
        "verificacao_pendente": "A verificação de acesso não terminou no prazo. Nenhuma consulta foi enviada.",
        "resposta_nao_confirmada": "A consulta foi enviada, mas a página de detalhes desse processo não foi confirmada. Confira a captura; isso não prova que o processo não existe.",
        "captura_indisponivel": "A página do processo foi identificada, mas não foi possível registrar a imagem. A comprovação ficou incompleta.",
        "pagina_indisponivel": "O portal do TJSP não ficou disponível nesta tentativa.",
        "erro_tecnico": "A consulta foi interrompida por uma falha técnica. Confira a última etapa registrada.",
    }.get(report.get("resultado"), "A abertura do processo não foi confirmada nesta tentativa.")


def consultar_pagina(page, report: dict, *, espera: int, etapa) -> int:
    numero = report["numero_consultado"]
    report["digitos_verificadores_validos"] = digitos_conferem(numero)
    print("TJSP: abrindo a consulta pública por número...", flush=True)
    response = page.goto(URL, wait_until="domcontentloaded", timeout=45000)
    if response and not response.ok:
        report["resultado"] = "pagina_indisponivel"
        etapa("Portal indisponível")
        return 1
    instancia = report.get("instancia_codigo", "SP")
    if page.locator("#selInstancia").input_value() != instancia:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=45000):
            page.locator("#selInstancia").select_option(instancia)
        page.wait_for_function("v => document.querySelector('#selInstancia')?.value === v && document.readyState !== 'loading'", arg=instancia)
        page.wait_for_load_state("domcontentloaded")
    if not oficial(page.url):
        raise RuntimeError("Destino inesperado")
    page.locator("#txtNumProcesso").fill(numero)
    report["instancia"] = "Tribunal de Justiça · 2º grau" if instancia == "TJSP" else "Primeiro grau"
    etapa("Número informado no TJSP")
    print("TJSP: aguardando a verificação de acesso; se solicitado, conclua na janela do tribunal...", flush=True)
    prazo = time.monotonic() + espera
    while time.monotonic() < prazo:
        # Espera o próprio portal. Não injeta tokens nem declara resolução automática.
        if page.locator(TOKEN_SELECTOR).evaluate_all("els => els.some(e => Boolean(e.value.trim()))"):
            report["resposta_widget_recebida"] = True
            break
        page.wait_for_timeout(500)
    else:
        report["resultado"] = "verificacao_pendente"
        etapa("Verificação pendente; consulta não enviada")
        return 1
    page.wait_for_timeout(800)  # permite que o widget pinte seu estado antes da captura
    etapa("Resposta da verificação recebida; aguardando consulta")
    print("TJSP: enviando o número do processo...", flush=True)
    texto_antes = page.locator("body").inner_text()
    def resposta_servidor(response):
        req = response.request
        original = req
        while original.redirected_from:
            original = original.redirected_from
        if req.is_navigation_request() and req.frame == page.main_frame and original.method == "POST" and oficial(response.url):
            report.update(resposta_consulta_recebida=True, http_status_consulta=response.status)
    page.on("response", resposta_servidor)
    page.get_by_role("button", name="Consultar", exact=True).click()
    report["consulta_enviada"] = True
    prazo = time.monotonic() + espera
    estaveis = {}
    def tela(candidate):
        return candidate.evaluate("""() => ({url:location.href, estado:document.readyState,
            texto:document.body?.innerText || '', formulario:Boolean(document.querySelector('#txtNumProcesso')?.getClientRects().length)})""")
    while time.monotonic() < prazo:
        for candidate in list(page.context.pages):
            if candidate.is_closed() or not oficial(candidate.url):
                continue
            try:
                snapshot = tela(candidate)
                if snapshot['estado'] != 'complete' or not snapshot['texto'].strip() or not oficial(snapshot['url']):
                    estaveis.pop(candidate, None)
                    continue
                previous = estaveis.get(candidate)
                estaveis[candidate] = snapshot
                if previous != snapshot:
                    continue  # exige a mesma página completa em duas leituras separadas
                text = snapshot['texto']
                formulario = snapshot['formulario']
                if digitos_conferem(numero) and detalhes_correspondem(candidate.url, text, numero, formulario):
                    frame = capturar_etapa(candidate, Path(report["_pasta"]), "Página do processo aberta no TJSP")
                    if tela(candidate) != snapshot:
                        continue
                    report.update(url_final=candidate.url.split("?")[0], numero_confirmado=numero,
                                  pagina_processo_confirmada=True, validacao_servidor_confirmada=True,
                                  pagina_seguinte_observada=True, captura_estavel=bool(frame),
                                  captura_resultado=frame, resultado="processo_aberto" if frame else "captura_indisponivel")
                    print("TJSP: processo aberto e número conferido.", flush=True)
                    return 0 if frame else 1
                simples = texto_simples(text)
                mensagem = ("Número inválido" if any(x in simples for x in ("numero do processo invalido", "numero de processo invalido", "numero invalido")) else
                            "Não existem informações disponíveis para os parâmetros informados" if "nao existem informacoes disponiveis para os parametros informados" in simples else
                            "Processo não encontrado" if any(x in simples for x in ("processo nao encontrado", "nenhum processo encontrado", "nao foi encontrado", "nao foram encontrados")) else None)
                # A resposta documentada comprova o avanço do formulário, mesmo se não houver processo.
                barreira = any(x in simples for x in ("verifique se voce e humano", "just a moment", "checking your browser"))
                if text.strip() and not barreira and (mensagem or not formulario) and text != texto_antes and report.get("resposta_consulta_recebida") and 200 <= report.get("http_status_consulta", 0) < 300:
                    mensagem = mensagem or "Página de retorno do TJSP"
                    frame = capturar_etapa(candidate, Path(report["_pasta"]), "Retorno do TJSP: " + mensagem.lower())
                    if tela(candidate) != snapshot:
                        continue
                    report.update(resultado="retorno_sem_processo" if frame else "captura_indisponivel",
                                  pagina_seguinte_observada=True, mensagem_portal=mensagem,
                                  url_final=candidate.url.split("?")[0], captura_resultado=frame, captura_estavel=bool(frame))
                    print("TJSP: retorno recebido e tela registrada.", flush=True)
                    return 0 if frame else 1
            except PlaywrightError:
                continue  # redirecionamento em andamento
        page.wait_for_timeout(500)
    report["resultado"] = "resposta_nao_confirmada"
    etapa("Retorno do TJSP; abertura do processo não confirmada")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processo", required=True, type=normalizar_processo)
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--instancia", choices=("SP", "TJSP"), default="SP")
    args = parser.parse_args(argv)
    pasta = ROOT / "evidencias_tjsp" / uuid4().hex[:12]
    pasta.mkdir(parents=True)
    print(f"Evidências: {pasta}", flush=True)
    report = dict(numero_consultado=args.processo, instancia_codigo=args.instancia, resultado="inconclusivo", consulta_enviada=False,
                  resposta_widget_recebida=False, pagina_processo_confirmada=False,
                  validacao_servidor_confirmada=False, data_hora_utc=datetime.now(timezone.utc).isoformat(), _pasta=str(pasta))
    inicio = time.monotonic()
    codigo = 1
    try:
        with sync_playwright() as p:
            with abrir_pagina(p, navegador=args.navegador, headless=args.headless, modo_playwright=False) as page:
                page.set_default_timeout(15000)
                page.on("dialog", lambda dialog: dialog.dismiss())
                try:
                    codigo = consultar_pagina(page, report, espera=80, etapa=lambda title: capturar_etapa(page, pasta, title))
                except Exception:
                    capturar_etapa(page, pasta, "Última página antes da interrupção")
                    raise
    except Exception as exc:
        report.update(resultado="erro_tecnico", erro_tipo=type(exc).__name__)
    report.pop("_pasta", None)
    report["duracao_segundos"] = round(time.monotonic() - inicio, 2)
    report["mensagem"] = mensagem_resultado(report)
    (pasta / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report["mensagem"], flush=True)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
