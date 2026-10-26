"""Preenche consultas e coleta resultados com CAPTCHA resolvido pelo operador."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4


ROOT = Path(__file__).resolve().parent


class ConsultaError(Exception):
    """Falha de configuração ou de consulta, sem resultado confirmado."""


def validar_config(config: dict, *, permitir_demo: bool = False) -> dict:
    if not isinstance(config, dict):
        raise ConsultaError("A configuração precisa ser um objeto JSON.")
    url = config.get("url", "")
    if not isinstance(url, str):
        raise ConsultaError("Informe a URL do site na configuração.")
    parsed = urlparse(url)
    if not (parsed.scheme in {"http", "https"} and parsed.hostname):
        if not (permitir_demo and url == (ROOT / "fixtures" / "consulta.html").as_uri()):
            raise ConsultaError("Informe uma URL HTTP ou HTTPS válida.")
    if parsed.hostname and parsed.hostname.endswith(".invalid"):
        raise ConsultaError("Substitua a URL de exemplo pelo endereço do site real.")
    for chave in ("campos", "campos_resultado"):
        mapping = config.get(chave)
        if not isinstance(mapping, dict) or not mapping:
            raise ConsultaError(f"Configure '{chave}' com nome e seletor de cada campo.")
        if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str)
               or not v.strip() for k, v in mapping.items()):
            raise ConsultaError(f"Os nomes e seletores de '{chave}' precisam ser textos não vazios.")
    for chave in ("botao_consultar", "resultado_pronto"):
        if not isinstance(config.get(chave), str) or not config[chave].strip():
            raise ConsultaError(f"Configure o seletor '{chave}'.")
    erro = config.get("erro_consulta")
    if erro is not None and (not isinstance(erro, str) or not erro.strip()):
        raise ConsultaError("O seletor 'erro_consulta' precisa ser um texto não vazio.")
    timeout = config.get("timeout_segundos", 30)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 300:
        raise ConsultaError("Use 'timeout_segundos' entre 1 e 300.")
    if config.get("navegador", "msedge") not in {"msedge", "chrome", "chromium"}:
        raise ConsultaError("Use o navegador 'msedge', 'chrome' ou 'chromium'.")
    return dict(config)


def config_demo() -> dict:
    return validar_config({
        "url": (ROOT / "fixtures" / "consulta.html").as_uri(),
        "navegador": "msedge",
        "campos": {"documento": "#documento"},
        "botao_consultar": "#consultar",
        "resultado_pronto": "#resultado",
        "erro_consulta": "#erro",
        "campos_resultado": {"documento": "#documento_resultado", "nome": "#nome", "situacao": "#situacao"},
        "timeout_segundos": 10,
    }, permitir_demo=True)


def aguardar_resultado(page, config: dict) -> dict[str, str]:
    deadline = time.monotonic() + config.get("timeout_segundos", 30)
    while time.monotonic() < deadline:
        if page.is_closed():
            raise ConsultaError("O navegador foi fechado antes de concluir a consulta.")
        seletor_erro = config.get("erro_consulta")
        if seletor_erro:
            erro = page.locator(seletor_erro)
            if erro.is_visible():
                raise ConsultaError(erro.inner_text().strip() or "O site recusou a consulta.")
        if page.locator(config["resultado_pronto"]).is_visible():
            resultado = {}
            for nome, seletor in config["campos_resultado"].items():
                valor = page.locator(seletor).inner_text().strip()
                if not valor:
                    raise ConsultaError(f"O campo de resultado '{nome}' ficou vazio; revise o seletor.")
                resultado[nome] = valor
            return resultado
        page.wait_for_timeout(150)
    raise ConsultaError("O resultado não apareceu no prazo. Confira a página e os seletores; nada foi exportado.")


def consultar_pagina(page, config: dict, valores: dict[str, str], confirmar: Callable[[str], str]) -> dict[str, str]:
    page.goto(config["url"], wait_until="domcontentloaded")
    confirmar("Se o site pedir login ou verificações antes do formulário, conclua no navegador. "
              "Quando o formulário estiver visível, pressione ENTER aqui. ")
    for nome, seletor in config["campos"].items():
        page.locator(seletor).fill(valores[nome])
    confirmar("Resolva o CAPTCHA no navegador. Deixe o botão Consultar sem clicar "
              "e pressione ENTER aqui para enviar a consulta. ")
    page.locator(config["botao_consultar"]).click()
    return aguardar_resultado(page, config)


def executar_consulta(
    config: dict,
    valores: dict[str, str],
    confirmar: Callable[[str], str] = input,
    *,
    headless: bool = False,
    permitir_demo: bool = False,
) -> dict[str, str]:
    config = validar_config(config, permitir_demo=permitir_demo)
    faltantes = set(config["campos"]) - set(valores)
    extras = set(valores) - set(config["campos"])
    if faltantes:
        raise ConsultaError("Faltam valores para: " + ", ".join(sorted(faltantes)))
    if extras:
        raise ConsultaError("Campos desconhecidos: " + ", ".join(sorted(extras)))
    if any(not isinstance(valor, str) or not valor.strip() for valor in valores.values()):
        raise ConsultaError("Os valores de consulta precisam ser textos não vazios.")
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError as exc:
        raise ConsultaError("Execute INSTALAR.ps1 para instalar o Playwright no ambiente isolado.") from exc

    try:
        with sync_playwright() as playwright:
            navegador = config.get("navegador", "msedge")
            browser = playwright.chromium.launch(
                channel=None if navegador == "chromium" else navegador,
                headless=headless,
            )
            try:
                context = browser.new_context(locale="pt-BR")
                page = context.new_page()
                page.set_default_timeout(config.get("timeout_segundos", 30) * 1000)
                return consultar_pagina(page, config, valores, confirmar)
            finally:
                browser.close()
    except PlaywrightError as exc:
        raise ConsultaError(f"Falha no navegador ou no seletor configurado: {exc}") from exc


def salvar_resultado(destino: Path, config: dict, valores: dict, dados: dict, *, demo: bool) -> Path:
    agora = datetime.now().astimezone()
    pasta = destino / f"{agora:%Y%m%d-%H%M%S}-{uuid4().hex[:10]}"
    pasta.mkdir(parents=True, exist_ok=False)
    payload = {"modo": "demonstracao" if demo else "site_configurado", "data_hora": agora.isoformat(),
               "url": config["url"], "consulta": valores, "resultado": dados}
    (pasta / "resultado.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with (pasta / "resultado.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        # A captura é texto. Evita que conteúdo do site seja tratado como fórmula no Excel.
        def texto_csv(valor):
            texto = str(valor)
            return "'" + texto if texto.lstrip().startswith(("=", "+", "-", "@")) else texto
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(texto_csv(chave) for chave in dados)
        writer.writerow(texto_csv(valor) for valor in dados.values())
    return pasta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="JSON com URL e seletores do site")
    parser.add_argument("--campo", action="append", default=[], metavar="NOME=VALOR")
    parser.add_argument("--demo", action="store_true", help="Usa somente uma página local com dados fictícios")
    parser.add_argument("--saida", type=Path, default=ROOT / "resultados")
    args = parser.parse_args(argv)
    try:
        if args.demo and args.config:
            raise ConsultaError("Escolha --demo ou --config, sem combinar os dois.")
        if args.demo:
            config = config_demo()
        elif args.config:
            config = validar_config(json.loads(args.config.read_text(encoding="utf-8-sig")))
        else:
            raise ConsultaError("Informe --demo ou --config caminho-do-arquivo.json.")
        valores = {}
        for campo in args.campo:
            nome, separador, valor = campo.partition("=")
            if not separador or not nome.strip() or not valor.strip():
                raise ConsultaError("Use --campo nome=valor, por exemplo --campo documento=123456.")
            if nome in valores:
                raise ConsultaError(f"O campo '{nome}' foi informado mais de uma vez.")
            valores[nome] = valor
        if args.demo and not valores:
            valores = {"documento": "DEMO-001"}
        print("DEMONSTRAÇÃO LOCAL: os dados são fictícios." if args.demo else "Consulta ao site configurado.")
        dados = executar_consulta(config, valores, permitir_demo=args.demo)
        pasta = salvar_resultado(args.saida, config, valores, dados, demo=args.demo)
        print(json.dumps(dados, ensure_ascii=False, indent=2))
        print(f"Arquivos JSON e CSV salvos em: {pasta}")
        return 0
    except (ConsultaError, OSError, ValueError) as exc:
        print(f"Consulta não concluída: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("Consulta cancelada pelo operador.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
