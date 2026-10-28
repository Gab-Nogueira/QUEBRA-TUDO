"""Consulta pública do TRF3 de primeiro grau por CNPJ, pelo navegador instalado."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from capturas_execucao import capturar_etapa
from testar_cloudflare import abrir_pagina

ROOT = Path(__file__).resolve().parent
URL = "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam"
DOCUMENTO = "fPP:dpDec:documentoParte"
CAMPO = f'[id="{DOCUMENTO}"]'
BOTAO = '[id="fPP:searchProcessos"]'
TABELA = '[id="fPP:processosTable"]'
NUMERO = re.compile(r"\b\d{7}-\d{2}\.\d{4}\.4\.03\.\d{4}\b")
TOTAL = re.compile(r"\b(\d[\d.]*)\s+resultados?\s+encontrados?\b", re.I)


def normalizar_cnpj(valor: str) -> str:
    if not isinstance(valor, str) or re.search(r"[^0-9. /-]", valor):
        raise ValueError("Informe um CNPJ numérico válido.")
    numero = re.sub(r"\D", "", valor)
    if len(numero) != 14 or len(set(numero)) == 1:
        raise ValueError("Informe um CNPJ válido com 14 dígitos.")
    for comprimento, pesos in ((12, (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)),
                               (13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))):
        resto = sum(int(digito) * peso for digito, peso in zip(numero[:comprimento], pesos)) % 11
        esperado = 0 if resto < 2 else 11 - resto
        if int(numero[comprimento]) != esperado:
            raise ValueError("Os dígitos verificadores do CNPJ não conferem.")
    return numero


def formatar_cnpj(numero: str) -> str:
    return f"{numero[:2]}.{numero[2:5]}.{numero[5:8]}/{numero[8:12]}-{numero[12:]}"


def total_exibido(texto: str) -> int | None:
    match = TOTAL.search(texto)
    return int(match.group(1).replace(".", "")) if match else None


def extrair_linhas(linhas: list[list[str]]) -> list[dict]:
    processos = {}
    for celulas in linhas:
        matches = [(i, list(dict.fromkeys(NUMERO.findall(celula)))) for i, celula in enumerate(celulas)]
        matches = [(i, nums) for i, nums in matches if nums]
        if len(matches) != 1 or len(matches[0][1]) != 1:
            continue
        indice, numeros = matches[0]
        numero = numeros[0]
        partes = [line.strip() for line in celulas[indice].splitlines() if line.strip()]
        titulo_indice = next(i for i, line in enumerate(partes) if numero in line)
        titulo = partes[titulo_indice]
        movimentacao = "\n".join(c.strip() for c in celulas[indice + 1:] if c.strip())
        if not movimentacao:
            raise ValueError(f"Última movimentação não identificada para {numero}.")
        data = re.search(r"\((\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})\)\s*$", movimentacao)
        registro = {
            "numero": numero,
            "classe": partes[titulo_indice - 1] if titulo_indice else "",
            "assunto": titulo.split(" - ", 1)[1] if " - " in titulo else "",
            "partes": " ".join(partes[titulo_indice + 1:]),
            "ultima_movimentacao": movimentacao,
            "data_ultima_movimentacao": data.group(1) if data else None,
        }
        if numero in processos and processos[numero] != registro:
            raise ValueError(f"Linhas divergentes para o processo {numero}.")
        processos[numero] = registro
    return list(processos.values())


def consulta_confirmada(relato: dict, cnpj: str = "") -> bool:
    esperado = cnpj or relato.get("cnpj_consultado")
    processos = relato.get("processos", [])
    total = relato.get("total_encontrados")
    return (
        relato.get("resultado") == "consulta_concluida"
        and relato.get("consulta_confirmada") is True
        and relato.get("resposta_pesquisa_recebida") is True
        and relato.get("http_status_consulta") == 200
        and relato.get("cnpj_formulario_confirmado") is True
        and bool(esperado) and relato.get("cnpj_consultado") == esperado == relato.get("cnpj_enviado")
        and relato.get("coleta_completa") is True
        and type(total) is int and total >= 0
        and isinstance(processos, list) and len(processos) == total
        and all(isinstance(item, dict) and isinstance(item.get("numero"), str) and NUMERO.fullmatch(item["numero"]) for item in processos)
        and len({item["numero"] for item in processos}) == total
    )


def mensagem_resultado(relato: dict) -> str:
    if consulta_confirmada(relato):
        total = relato["total_encontrados"]
        if total == 0:
            return "O TRF3 respondeu à pesquisa e não exibiu processos públicos para este CNPJ. Isso não comprova inexistência de processos."
        return f"O TRF3 retornou {total} processos públicos para o CNPJ informado. A lista e a última movimentação exibida foram coletadas."
    return {
        "falha_rede": "A conexão com o TRF3 falhou. A pesquisa não foi confirmada; não interpretar como ausência de processos.",
        "coleta_parcial": "O TRF3 respondeu, mas a lista coletada está incompleta. Confira o total e os registros disponíveis.",
        "verificacao_pendente": "A verificação do site não foi concluída. A consulta não foi confirmada.",
        "resposta_nao_confirmada": "O TRF3 não apresentou uma resposta completa no prazo. A pesquisa não foi confirmada.",
        "interrompido": "A consulta foi interrompida antes da conclusão.",
        "erro_tecnico": "Um erro técnico impediu concluir a pesquisa. Confira o diagnóstico desta tentativa.",
    }.get(relato.get("resultado"), "A consulta não foi confirmada.")


def pedido_da_pesquisa(request, cnpj: str) -> bool:
    parsed = urlparse(request.url)
    if request.method != "POST" or parsed.hostname != "pje1g.trf3.jus.br" or parsed.path.split(";", 1)[0] != urlparse(URL).path:
        return False
    data = parse_qs(request.post_data or "")
    valor = data.get(DOCUMENTO, [""])[0]
    # RichFaces envia uma ação fPP:j_id... que muda conforme a página. O id
    # visual do botão não é o nome do parâmetro enviado pelo formulário.
    return (re.sub(r"\D", "", valor) == cnpj and data.get("fPP") == ["fPP"]
            and "AJAXREQUEST" in data and "javax.faces.ViewState" in data)


def observar_protecao(page, relato: dict, etapa: str):
    """Registra presença, sem guardar valores de cookies ou afirmar validade."""
    nomes = {cookie["name"] for cookie in page.context.cookies([URL])}
    relato["protecao_observada"].append({
        "etapa": etapa,
        "cookies_presentes": [nome for nome in ("_abck", "ak_bmsc", "bm_sz", "bm_sv") if nome in nomes],
    })
    for fornecedor, seletor in (
        ("recaptcha", 'iframe[src*="/recaptcha/"]'),
        ("hcaptcha", 'iframe[src*="hcaptcha.com"]'),
    ):
        if any(frame.is_visible() for frame in page.locator(seletor).all()):
            relato["desafio_interativo_observado"] = True
            relato["fornecedor_desafio"] = fornecedor
    # A presença dos cookies não prova liberação. A confirmação depende da
    # resposta da pesquisa e do conteúdo realmente exibido pelo tribunal.


def preparar_formulario(page, cnpj: str, relato: dict):
    resposta = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    relato["http_status"] = resposta.status if resposta else None
    if resposta and not resposta.ok:
        raise RuntimeError("A página de consulta respondeu com erro HTTP.")
    page.locator(CAMPO).wait_for(state="visible", timeout=30000)
    radio = page.locator('input[name="tipoMascaraDocumento"][onclick*="CNPJ"]')
    radio.check()
    page.locator(CAMPO).fill(formatar_cnpj(cnpj))
    page.locator(CAMPO).press("Tab")
    if not radio.is_checked() or re.sub(r"\D", "", page.locator(CAMPO).input_value()) != cnpj:
        raise ValueError("O formulário não preservou o CNPJ informado.")
    relato["cnpj_formulario_confirmado"] = True
    # Dá tempo aos recursos normais da página para terminarem a inicialização.
    page.wait_for_timeout(3000)
    observar_protecao(page, relato, "formulario_pronto")


def pesquisar(page, cnpj: str, relato: dict, pasta: Path) -> int:
    print("TRF3: abrindo a consulta pública de primeiro grau...", flush=True)
    preparar_formulario(page, cnpj, relato)
    capturar_etapa(page, pasta, "CNPJ preenchido na consulta pública do TRF3")
    tentativa = {}

    def receber(response):
        if pedido_da_pesquisa(response.request, cnpj):
            tentativa["http_status"] = response.status
            relato.update(cnpj_enviado=cnpj, http_status_consulta=response.status,
                          resposta_pesquisa_recebida=response.status == 200)

    def falhar(request):
        if pedido_da_pesquisa(request, cnpj):
            tentativa["erro_rede"] = request.failure

    page.on("response", receber)
    page.on("requestfailed", falhar)
    try:
        for numero in (1, 2):
            tentativa = {"numero": numero}
            relato["tentativas"].append(tentativa)
            relato["resposta_pesquisa_recebida"] = False
            print(f"TRF3: enviando a pesquisa por CNPJ (tentativa {numero})...", flush=True)
            page.locator(BOTAO).click()
            prazo = time.monotonic() + 60
            while time.monotonic() < prazo:
                texto = page.locator(TABELA).inner_text()
                total = total_exibido(texto)
                if total is not None and relato["resposta_pesquisa_recebida"]:
                    linhas = page.locator(TABELA + " tr").evaluate_all("""els => els.filter(row => !row.querySelector('tr')).map(row =>
                        Array.from(row.children).filter(e => e.tagName === 'TD').map(e => e.innerText))""")
                    processos = extrair_linhas(linhas)
                    relato.update(total_encontrados=total, processos=processos,
                                  coleta_completa=len(processos) == total,
                                  consulta_confirmada=True,
                                  resultado="consulta_concluida" if len(processos) == total else "coleta_parcial")
                    capturar_etapa(page, pasta, "Resultado da pesquisa por CNPJ no TRF3")
                    observar_protecao(page, relato, "pesquisa_respondida")
                    print(f"TRF3: resultado recebido; {len(processos)} de {total} processos coletados.", flush=True)
                    return 0 if consulta_confirmada(relato) else 1
                if tentativa.get("erro_rede"):
                    break
                if tentativa.get("http_status", 200) >= 400:
                    break
                page.wait_for_timeout(500)
            observar_protecao(page, relato, "pesquisa_sem_confirmacao")
            if tentativa.get("erro_rede") and numero == 1:
                print("TRF3: falha de conexão; uma nova tentativa da mesma pesquisa será feita...", flush=True)
                page.wait_for_timeout(3000)
                preparar_formulario(page, cnpj, relato)
                continue
            relato["resultado"] = "falha_rede" if tentativa.get("erro_rede") else "verificacao_pendente" if relato["desafio_interativo_observado"] else "resposta_nao_confirmada"
            return 1
    finally:
        page.remove_listener("response", receber)
        page.remove_listener("requestfailed", falhar)
    return 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cnpj", required=True, type=normalizar_cnpj)
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)
    pasta = ROOT / "evidencias_trf3" / uuid4().hex[:12]
    pasta.mkdir(parents=True, exist_ok=False)
    print(f"Evidências: {pasta}", flush=True)
    relato = {
        "url": URL, "data_hora_utc": datetime.now(timezone.utc).isoformat(),
        "cnpj_consultado": args.cnpj, "cnpj_formatado": formatar_cnpj(args.cnpj),
        "cnpj_formulario_confirmado": False, "cnpj_enviado": None,
        "consulta_confirmada": False, "resposta_pesquisa_recebida": False,
        "coleta_completa": False, "total_encontrados": None, "processos": [],
        "desafio_interativo_observado": False, "protecao_observada": [], "intervencao_humana": False,
        "servico_externo_de_resolucao": False, "resultado": "inconclusivo", "tentativas": [],
        "navegador": args.navegador, "headless": args.headless,
        "escopo": "consulta_publica_trf3_primeiro_grau_por_cnpj",
    }
    inicio = time.monotonic()
    codigo = 2
    try:
        with sync_playwright() as playwright:
            with abrir_pagina(playwright, navegador=args.navegador, headless=args.headless, modo_playwright=False) as page:
                page.set_default_timeout(10000)
                try:
                    codigo = pesquisar(page, args.cnpj, relato, pasta)
                finally:
                    if not page.is_closed():
                        try:
                            page.screenshot(path=str(pasta / "tela.png"), full_page=True, timeout=5000)
                        except PlaywrightError:
                            pass
    except KeyboardInterrupt:
        relato["resultado"] = "interrompido"
        codigo = 2
    except Exception as exc:
        relato.update(resultado="erro_tecnico", erro_tipo=type(exc).__name__)
        codigo = 2
    relato["duracao_segundos"] = round(time.monotonic() - inicio, 2)
    relato["mensagem"] = mensagem_resultado(relato)
    (pasta / "resultado.json").write_text(json.dumps(relato, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relato, ensure_ascii=False, indent=2), flush=True)
    print("\n" + relato["mensagem"], flush=True)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
