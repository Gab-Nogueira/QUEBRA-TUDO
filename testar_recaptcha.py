"""Bancada reCAPTCHA: áudio com modelo local, clique simples ou seleção interativa."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import time
from uuid import uuid4

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from recaptcha_audio import ResolucaoAudioError, TranscritorLocal, resolver_audio
from capturas_execucao import capturar_etapa


URL = "https://www.google.com/recaptcha/api2/demo"
ROOT = Path(__file__).resolve().parent


def mensagem_resultado(relato: dict, codigo: int) -> str:
    if codigo == 0 and relato.get("validacao_servidor_confirmada"):
        if relato.get("resolucao_automatica_local"):
            return "DEU CERTO! O reCAPTCHA foi resolvido sozinho e o Google confirmou a verificação."
        return "DEU CERTO! O Google confirmou a verificação do reCAPTCHA."
    if codigo == 1:
        return "NÃO DEU CERTO. O reCAPTCHA não foi concluído nesta tentativa."
    return "TESTE INCONCLUSIVO. Houve um erro ou a aprovação pelo Google não foi confirmada."


def selecionar_imagens(page, pasta: Path) -> bool:
    """Bancada interativa: a seleção é orientada pelo operador, sem modelo embutido."""
    desafio = page.frame_locator('iframe[src*="/recaptcha/api2/bframe"]')
    caixa = page.frame_locator('iframe[src*="/recaptcha/api2/anchor"]').locator("#recaptcha-anchor")
    for etapa in range(1, 16):
        if caixa.get_attribute("aria-checked") == "true":
            return True
        page.screenshot(path=str(pasta / f"etapa-{etapa:02d}.png"), full_page=True)
        print(f"ETAPA {etapa}: {pasta / f'etapa-{etapa:02d}.png'}", flush=True)
        print(desafio.locator("body").inner_text(), flush=True)
        comando = input("Posições da grade em ordem de leitura (ex.: 1 5 9), v para verificar, q para sair: ").strip()
        if comando.lower() == "q":
            return False
        if comando.lower() == "v":
            desafio.locator("#recaptcha-verify-button").click()
        else:
            indices = [int(item) - 1 for item in comando.split()]
            tiles = desafio.locator(".rc-imageselect-tile")
            if any(indice < 0 or indice >= tiles.count() for indice in indices):
                raise ValueError("Posição fora da grade.")
            for indice in indices:
                tiles.nth(indice).click()
        page.wait_for_timeout(2200)
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modos = parser.add_mutually_exclusive_group()
    modos.add_argument("--interativo", action="store_true", help="Seleção de imagens orientada pelo terminal")
    modos.add_argument("--apenas-clique", action="store_true", help="Diagnóstico: clica uma vez e não resolve o desafio")
    modos.add_argument("--automatico", action="store_true", help="Áudio com reconhecimento local, modo padrão")
    parser.add_argument("--modelo", choices=("tiny.en", "base.en", "small.en"), default="base.en")
    parser.add_argument("--preparar-modelo", action="store_true", help="Instala o modelo local sem abrir o navegador")
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--headless", action="store_true", help="Executa o Chrome sem abrir uma janela")
    args = parser.parse_args(argv)
    automatico = not args.interativo and not args.apenas_clique
    pasta = ROOT / "evidencias_recaptcha" / uuid4().hex[:12]
    pasta.mkdir(parents=True, exist_ok=False)
    print(f"Evidências: {pasta}", flush=True)
    relato = {
        "url": URL,
        "data_hora_utc": datetime.now(timezone.utc).isoformat(),
        "metodo": ("Reconhecimento local do áudio" if automatico else "Um clique normal na caixa"),
        "navegador": args.navegador,
        "modo": "automatico_audio_local" if automatico else "interativo" if args.interativo else "apenas_clique",
        "resultado": "inconclusivo",
        "checkbox_marcado": False,
        "resposta_emitida": False,
        "desafio_adicional_visivel": False,
        "desafio_adicional_foi_exigido": False,
        "resolucao_automatica_local": False,
        "intervencao_humana": args.interativo,
        "validacao_servidor_confirmada": False,
    }
    codigo = 2
    page = None
    try:
        transcritor = TranscritorLocal(args.modelo) if automatico or args.preparar_modelo else None
        if transcritor:
            relato["modelo_local"] = args.modelo
        if args.preparar_modelo:
            print("Modelo pronto. Execute TESTAR_RECAPTCHA.cmd para iniciar a resolução automática.")
            return 0
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=None if args.navegador == "chromium" else args.navegador, headless=args.headless)
            try:
                # A transcrição usa o modelo de inglês; o widget recebe a mesma preferência.
                context = browser.new_context(locale="en-US", viewport={"width": 1100, "height": 850})
                page = context.new_page()
                page.set_default_timeout(20000)
                resposta = page.goto(URL, wait_until="domcontentloaded", timeout=30000)
                relato["http_status"] = resposta.status if resposta else None
                caixa = page.frame_locator('iframe[src*="/recaptcha/api2/anchor"]').locator("#recaptcha-anchor")
                caixa.wait_for(state="visible")
                capturar_etapa(page, pasta, "Demonstração oficial do Google")
                print("Clicando uma vez na caixa da demonstração oficial...", flush=True)
                caixa.click()
                prazo = time.monotonic() + 20
                while time.monotonic() < prazo:
                    relato["checkbox_marcado"] = caixa.get_attribute("aria-checked") == "true"
                    resposta_widget = page.locator('[name="g-recaptcha-response"]')
                    relato["resposta_emitida"] = bool(resposta_widget.count() and resposta_widget.input_value())
                    desafio = page.locator('iframe[src*="/recaptcha/api2/bframe"]')
                    relato["desafio_adicional_visivel"] = bool(desafio.count() and desafio.is_visible())
                    relato["desafio_adicional_foi_exigido"] |= relato["desafio_adicional_visivel"]
                    if relato["desafio_adicional_visivel"]:
                        capturar_etapa(page, pasta, "Desafio apresentado pelo Google")
                        if args.interativo:
                            relato["metodo"] = "Seleção de imagens orientada pelo operador"
                            selecionar_imagens(page, pasta)
                        elif automatico:
                            relato["resolucao_automatica_local"] = resolver_audio(page, pasta, transcritor, relato)
                        relato["checkbox_marcado"] = caixa.get_attribute("aria-checked") == "true"
                        relato["resposta_emitida"] = bool(resposta_widget.count() and resposta_widget.input_value())
                    if relato["checkbox_marcado"] and relato["resposta_emitida"]:
                        # Só confirma aprovação após a resposta do formulário oficial.
                        with page.expect_navigation(wait_until="domcontentloaded") as navegacao:
                            page.locator("#recaptcha-demo-submit").click()
                        validacao = navegacao.value
                        relato["http_status_validacao"] = validacao.status if validacao else None
                        texto = page.locator("body").inner_text()
                        relato["validacao_servidor_confirmada"] = bool(validacao and validacao.ok and any(
                            mensagem in texto for mensagem in ("Verification Success", "Verificação concluída")
                        ))
                        relato["confirmacao_texto"] = texto[:300]
                        capturar_etapa(page, pasta, "Resposta do formulário do Google")
                        relato["resolucao_automatica_local"] = automatico and relato["validacao_servidor_confirmada"]
                        if relato["validacao_servidor_confirmada"]:
                            relato["desafio_adicional_visivel"] = False
                        relato["resultado"] = ("aprovado_na_demonstracao" if relato["validacao_servidor_confirmada"]
                                                 else "checkbox_marcado_sem_confirmacao_do_servidor")
                        codigo = 0 if relato["validacao_servidor_confirmada"] else 2
                        break
                    if relato["desafio_adicional_visivel"]:
                        relato["resultado"] = "desafio_adicional_exigido"
                        codigo = 1
                        break
                    page.wait_for_timeout(250)
                else:
                    relato["resultado"] = "nao_liberou_no_prazo"
                    codigo = 1
            except ResolucaoAudioError as exc:
                relato["resultado"] = exc.motivo
                relato["erro"] = str(exc)
                codigo = 1
            finally:
                if page and not page.is_closed():
                    try:
                        relato["url_final"] = page.url
                        page.screenshot(path=str(pasta / "tela.png"), full_page=True, timeout=5000)
                    except PlaywrightError:
                        pass
                browser.close()
    except (Exception, KeyboardInterrupt) as exc:
        relato["erro"] = str(exc) or "Execução interrompida."
    (pasta / "resultado.json").write_text(json.dumps(relato, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(relato, ensure_ascii=False, indent=2))
    print(f"Evidências: {pasta}")
    print("\n" + "=" * 75)
    print(mensagem_resultado(relato, codigo))
    print("=" * 75, flush=True)
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
