"""Consulta pública do STJ pelo nome da parte, com execução local no navegador."""

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
from testar_cloudflare import abrir_pagina, acionar_caixa, frames_cloudflare

ROOT = Path(__file__).resolve().parent
URL = "https://processo.stj.jus.br/processo/pesquisa/?aplicacao=processos.ea"
CAMPO = "#idParteNome"
CONTEM = "#idComboFoneticaPhonosParte_2"
BOTAO = "#idBotaoPesquisarFormularioExtendido"
REGISTRO = re.compile(r"\d{4}/\d{7}-\d")
TOTAL = re.compile(r"Pesquisa resultou em\s+(\d[\d.]*)\s+registro\(s\)!", re.I)
LINHA = re.compile(
    r"^(?P<classe>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ .-]{0,60}?)\s+"
    r"(?P<numero>\d+)/(?P<uf>[A-Z]{2})\s+(?P<registro>\d{4}/\d{7}-\d)\s+"
    r"(?P<autuacao>\d{2}/\d{2}/\d{4})\s+(?P<tipo>[^\n]+)$", re.M
)


def normalizar_nome(valor: str) -> str:
    if not isinstance(valor, str) or any(ord(c) < 32 and c not in "\t\r\n" for c in valor):
        raise ValueError("Informe o nome da parte como texto.")
    nome = " ".join(valor.split()).upper()
    if not 3 <= len(nome) <= 160 or sum(c.isalpha() for c in nome) < 3:
        raise ValueError("Informe o nome da parte, entre 3 e 160 caracteres. O STJ não pesquisa por CPF/CNPJ.")
    return nome


def total_exibido(texto: str) -> int | None:
    match = TOTAL.search(texto)
    return int(match.group(1).replace(".", "")) if match else None


def nome_no_resultado(texto: str, nome: str) -> bool:
    titulo = f"Listando processos relacionados a(s) parte(s) com nome {nome}."
    return titulo.casefold() in " ".join(texto.split()).casefold()


def extrair_processos(texto: str) -> list[dict]:
    """Extrai só a listagem pública; não inventa movimentação ou vínculo ao CNPJ."""
    texto = re.split(r"\n\s*Versão\s", texto, maxsplit=1)[0]
    matches = list(LINHA.finditer(texto))
    processos = {}
    for i, match in enumerate(matches):
        item = {k: v.strip() for k, v in match.groupdict().items()}
        item["numero"] = f"{item['classe']} {item['numero']}/{item['uf']}"
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        partes = [linha.strip() for linha in texto[match.end():fim].splitlines()
                  if re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ. ]+:", linha.strip())]
        if not partes:
            raise ValueError("As partes de um registro não foram identificadas na listagem.")
        item["partes"] = "\n".join(partes)
        registro = item["registro"]
        if registro in processos and processos[registro] != item:
            raise ValueError("O STJ exibiu registros divergentes com o mesmo número de registro.")
        processos[registro] = item
    return list(processos.values())


def consulta_confirmada(relato: dict, nome: str = "") -> bool:
    esperado = nome or relato.get("nome_consultado")
    processos = relato.get("processos")
    total = relato.get("total_encontrados")
    return bool(
        relato.get("resultado") == "consulta_concluida"
        and relato.get("consulta_confirmada") is True
        and relato.get("resposta_pesquisa_recebida") is True
        and relato.get("http_status_consulta") == 200
        and relato.get("nome_formulario_confirmado") is True
        and relato.get("nome_resultado_confirmado") is True
        and esperado and relato.get("nome_consultado") == esperado == relato.get("nome_enviado")
        and relato.get("criterio") == "contem"
        and relato.get("coleta_completa") is True
        and type(total) is int and total >= 0
        and isinstance(processos, list) and len(processos) == total
        and all(isinstance(p, dict) and isinstance(p.get("registro"), str)
                and REGISTRO.fullmatch(p["registro"]) and p.get("numero") for p in processos)
        and len({p["registro"] for p in processos}) == total
    )


def mensagem_resultado(relato: dict) -> str:
    if consulta_confirmada(relato):
        total = relato["total_encontrados"]
        return (f"O STJ retornou {total} registros públicos para o nome pesquisado. "
                "A pesquisa por nome não confirma o vínculo dos registros a um CNPJ.") if total else (
                "O STJ respondeu sem registros públicos para o nome pesquisado. Isso não comprova inexistência de processos.")
    return {
        "coleta_parcial": "O STJ respondeu, mas a lista coletada está incompleta. Confira os registros disponíveis.",
        "verificacao_pendente": "A verificação do site não foi concluída. A consulta ao STJ não foi confirmada.",
        "aplicacao_indisponivel": "O formulário do STJ abriu, mas seus componentes não terminaram de carregar. A pesquisa não foi enviada.",
        "falha_rede": "A conexão com o STJ falhou. Isso não significa ausência de processos.",
        "resposta_nao_confirmada": "O STJ não apresentou uma resposta completa no prazo. A consulta não foi confirmada.",
        "erro_tecnico": "Um erro técnico impediu concluir a consulta ao STJ.",
        "interrompido": "A consulta ao STJ foi interrompida.",
    }.get(relato.get("resultado"), "A consulta ao STJ não foi confirmada.")


def pedido_da_pesquisa(request, nome: str) -> bool:
    parsed = urlparse(request.url)
    if request.method != "POST" or parsed.hostname != "processo.stj.jus.br" or parsed.path != "/processo/pesquisa/":
        return False
    data = parse_qs(request.post_data or "")
    return (data.get("parteNome") == [nome] and data.get("aplicacao") == ["processos.ea"]
            and data.get("opcoesFoneticaPhonosParte") == ["2"]
            and data.get("acao") == ["pushconsultarprocessoconsultalimitenaoatendidasjaincluidas"])


def aguardar_formulario(page, relato: dict, pasta: Path) -> bool:
    print("STJ: abrindo a consulta pública...", flush=True)
    relato["tentativas_abertura"] = []
    relato["verificacao_inicial_observada"] = False
    for numero in (1, 2):
        resposta = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        status = resposta.status if resposta else None
        if numero == 1:
            relato["http_status_inicial"] = status
        relato["verificacao_inicial_observada"] |= status == 403
        tentativa = {"numero": numero, "http_status": status, "formulario_detectado": False, "aplicacao_inicializada": False}
        relato["tentativas_abertura"].append(tentativa)
        prazo = time.monotonic() + 60
        acionado = False
        incompleto_desde = None
        while time.monotonic() < prazo:
            if page.locator(CAMPO).is_visible():
                tentativa["formulario_detectado"] = True
                if "{{cabecalhoErro}}" not in page.locator("body").inner_text():
                    tentativa["aplicacao_inicializada"] = True
                    relato["formulario_carregado"] = True
                    return True
                if incompleto_desde is None:
                    incompleto_desde = time.monotonic()
                if time.monotonic() - incompleto_desde >= 15:
                    break
            frames = frames_cloudflare(page)
            if frames and not acionado:
                relato["verificacao_inicial_observada"] = True
                try:
                    acionado = bool(acionar_caixa(page, frames[0]))
                except PlaywrightError:
                    pass
            page.wait_for_timeout(500)
        if tentativa["formulario_detectado"] and numero == 1:
            capturar_etapa(page, pasta, "Formulário do STJ carregado parcialmente")
            print("STJ: recarregando o formulário após carregamento incompleto...", flush=True)
            continue
        capturar_etapa(page, pasta, "Formulário do STJ indisponível nesta tentativa")
        relato["resultado"] = ("aplicacao_indisponivel" if tentativa["formulario_detectado"] else
                               "verificacao_pendente" if relato["verificacao_inicial_observada"] else "resposta_nao_confirmada")
        break
    return False


def verificar_google(page, relato: dict, pasta: Path):
    anchor = page.locator('iframe[src*="/recaptcha/api2/anchor"]')
    desafio = page.locator('iframe[src*="/recaptcha/api2/bframe"]')
    if not anchor.count():
        return
    relato["recaptcha_observado"] = True
    caixa = page.frame_locator('iframe[src*="/recaptcha/api2/anchor"]').locator("#recaptcha-anchor")
    if caixa.is_visible() and not relato.get("recaptcha_acionado"):
        print("STJ: verificando o reCAPTCHA apresentado...", flush=True)
        caixa.click()
        relato["recaptcha_acionado"] = True
        capturar_etapa(page, pasta, "Verificação do Google apresentada pelo STJ")
    if desafio.count() and desafio.is_visible() and not relato.get("audio_tentado"):
        from recaptcha_audio import ResolucaoAudioError, TranscritorLocal, resolver_audio
        relato["desafio_interativo_observado"] = True
        relato["audio_tentado"] = True
        try:
            relato["audio_aceito_pelo_widget"] = resolver_audio(page, pasta, TranscritorLocal(), relato)
        except ResolucaoAudioError as exc:
            relato["motivo_verificacao"] = exc.motivo
        except PlaywrightError:
            # O callback do site pode navegar antes da última leitura do widget.
            # Só a resposta da pesquisa abaixo pode confirmar a consulta.
            relato["leitura_widget_interrompida"] = True


def pesquisar(page, nome: str, relato: dict, pasta: Path) -> int:
    if not aguardar_formulario(page, relato, pasta):
        return 1
    page.locator(CAMPO).fill(nome)
    page.locator(CONTEM).check()
    if page.locator(CAMPO).input_value() != nome or not page.locator(CONTEM).is_checked():
        raise ValueError("O formulário não preservou o nome ou critério informado.")
    relato["nome_formulario_confirmado"] = True
    capturar_etapa(page, pasta, "Nome da parte preenchido na consulta pública do STJ")

    def receber(response):
        if pedido_da_pesquisa(response.request, nome):
            relato.update(nome_enviado=nome, http_status_consulta=response.status,
                          resposta_pesquisa_recebida=response.status == 200)

    def falhar(request):
        if pedido_da_pesquisa(request, nome):
            relato["erro_rede"] = request.failure

    page.on("response", receber)
    page.on("requestfailed", falhar)
    try:
        print("STJ: enviando a pesquisa por nome da parte...", flush=True)
        page.locator(BOTAO).click()
        prazo = time.monotonic() + 90
        while time.monotonic() < prazo:
            texto = page.locator("body").inner_text()
            total = total_exibido(texto)
            if total is not None and relato["resposta_pesquisa_recebida"] and nome_no_resultado(texto, nome):
                processos = extrair_processos(texto)
                relato.update(nome_resultado_confirmado=True, total_encontrados=total, processos=processos,
                              coleta_completa=len(processos) == total, consulta_confirmada=True,
                              resultado="consulta_concluida" if len(processos) == total else "coleta_parcial")
                capturar_etapa(page, pasta, "Resultado da pesquisa por nome no STJ")
                print(f"STJ: resultado recebido; {len(processos)} de {total} registros coletados.", flush=True)
                return 0 if consulta_confirmada(relato) else 1
            if relato.get("erro_rede"):
                relato["resultado"] = "falha_rede"
                return 1
            verificar_google(page, relato, pasta)
            if relato.get("motivo_verificacao"):
                break
            page.wait_for_timeout(500)
        relato["resultado"] = "verificacao_pendente" if relato["recaptcha_observado"] else "resposta_nao_confirmada"
        return 1
    finally:
        page.remove_listener("response", receber)
        page.remove_listener("requestfailed", falhar)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parte", required=True, type=normalizar_nome)
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args(argv)
    pasta = ROOT / "evidencias_stj" / uuid4().hex[:12]
    pasta.mkdir(parents=True, exist_ok=False)
    print(f"Evidências: {pasta}", flush=True)
    relato = dict(url=URL, data_hora_utc=datetime.now(timezone.utc).isoformat(), nome_consultado=args.parte,
                  nome_enviado=None, criterio="contem", nome_formulario_confirmado=False, nome_resultado_confirmado=False,
                  resposta_pesquisa_recebida=False, consulta_confirmada=False, coleta_completa=False,
                  total_encontrados=None, processos=[], formulario_carregado=False, recaptcha_observado=False,
                  desafio_interativo_observado=False, intervencao_humana=False, servico_externo_de_resolucao=False,
                  vinculo_cnpj_verificado=False, resultado="inconclusivo", navegador=args.navegador,
                  escopo="consulta_publica_stj_nome_da_parte")
    inicio = time.monotonic()
    codigo = 2
    try:
        with sync_playwright() as playwright:
            with abrir_pagina(playwright, navegador=args.navegador, headless=args.headless, modo_playwright=False) as page:
                page.set_default_timeout(10000)
                try:
                    codigo = pesquisar(page, args.parte, relato, pasta)
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
    print(relato["mensagem"], flush=True)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
