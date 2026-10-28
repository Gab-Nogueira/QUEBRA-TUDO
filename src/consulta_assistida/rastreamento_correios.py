"""Lê o CAPTCHA dos Correios e consulta um código de rastreamento quando informado."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import re
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from .captcha_letras import LeitorLetras

URL = "https://rastreamento.correios.com.br/app/index.php"


def normalizar_objeto(valor: str) -> str:
    codigo = re.sub(r"\s+", "", valor).upper()
    if codigo and not re.fullmatch(r"[A-Z]{2}\d{9}[A-Z]{2}", codigo):
        raise ValueError("Informe um código de rastreamento com 13 caracteres, como AA123456785BR. CPF/CNPJ exige login nos Correios.")
    return codigo


def resumir_rastreamento(retorno: dict, solicitado: str, *, hoje: date | None = None) -> dict:
    codigo = retorno.get("codObjeto", "")
    if codigo != solicitado:
        raise ValueError("O código retornado pelos Correios não corresponde ao consultado.")
    eventos = retorno.get("eventos")
    if not isinstance(eventos, list) or not eventos or any(not isinstance(evento, dict) for evento in eventos):
        raise ValueError("Os Correios não retornaram eventos de rastreamento para este objeto.")

    def data_evento(evento):
        valor = evento.get("dtHrCriado", "")
        return str(valor.get("date", "") if isinstance(valor, dict) else valor)

    ultimo = max(eventos, key=data_evento)

    def local(unidade):
        unidade = unidade if isinstance(unidade, dict) else {}
        endereco = unidade.get("endereco") or {}
        cidade_uf = " / ".join(str(endereco[chave]) for chave in ("cidade", "uf") if endereco.get(chave))
        return " - ".join(str(item) for item in (unidade.get("nome") or unidade.get("tipo"), cidade_uf) if item)

    previsao = retorno.get("dtPrevista") or retorno.get("dataPrevista") or "Não informada pelos Correios"
    observacao_previsao = None
    # Calendário de Brasília para as consultas desta ferramenta.
    hoje = hoje or datetime.now(timezone(timedelta(hours=-3))).date()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            data_previsao = datetime.strptime(str(previsao)[:10], formato).date()
        except ValueError:
            continue
        if data_previsao < hoje:
            observacao_previsao = "A previsão informada já passou. Esta consulta não confirma uma nova data de entrega."
        break
    return {"codigo": codigo, "situacao": ultimo.get("descricao") or "Não informada",
            "ultimo_local_informado": local(ultimo.get("unidade")) or "Não informado",
            "em_transito_para": local(ultimo.get("unidadeDestino")) or None,
            "ultima_atualizacao": data_evento(ultimo) or "Não informada",
            "previsao_entrega": previsao,
            "observacao_previsao": observacao_previsao,
            "quantidade_eventos": len(eventos)}


def resposta_rastreamento(response) -> bool:
    url = urlparse(response.url)
    return url.hostname == "rastreamento.correios.com.br" and url.path == "/app/resultado.php"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objeto", default="", help="Opcional: código de rastreamento para consultar")
    parser.add_argument("--navegador", choices=("chrome", "msedge", "chromium"), default="chrome")
    parser.add_argument("--manter-aberto", action="store_true", help="Aguarda ENTER antes de fechar a janela")
    parser.add_argument("--headless", action="store_true", help="Executa o Chrome sem abrir uma janela")
    parser.add_argument("--sem-copiar", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--json-stdout", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    relato = {"url": URL, "data_hora_utc": datetime.now(timezone.utc).isoformat(), "resultado": "inconclusivo",
              "consulta_confirmada": False, "captcha_validado_pelo_servidor": False, "tentativas": []}
    codigo_saida = 2
    try:
        objeto = normalizar_objeto(args.objeto)
        relato["codigo_consultado"] = objeto or None
        leitor = LeitorLetras()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=None if args.navegador == "chromium" else args.navegador, headless=args.headless)
            page = None
            try:
                page = browser.new_page(locale="pt-BR", viewport={"width": 1280, "height": 900})
                page.set_default_timeout(20000)
                resposta = page.goto(URL, wait_until="domcontentloaded", timeout=45000)
                relato["http_status"] = resposta.status if resposta else None
                for tentativa in range(1, 4 if objeto else 2):
                    imagem = page.locator("#captcha_image")
                    imagem.wait_for(state="visible")
                    imagem.evaluate("img => img.decode()")
                    conteudo = imagem.screenshot()
                    leitura = leitor.ler(conteudo)
                    relato["tentativas"].append(leitura)
                    print(f"\nCAPTCHA RECONHECIDO: {leitura['texto']}", flush=True)
                    if leitura["alternativas"]:
                        print("Outras leituras possíveis: " + ", ".join(leitura["alternativas"]))
                    page.locator("#captcha").fill(leitura["texto"])
                    if not objeto:
                        relato["resultado"] = "leitura_realizada_sem_consulta"
                        codigo_saida = 0
                        break
                    page.locator("#objeto").fill(objeto)
                    src_anterior = imagem.get_attribute("src")
                    with page.expect_response(resposta_rastreamento, timeout=30000) as retorno:
                        page.locator("#b-pesquisar").click()
                    resposta_consulta = retorno.value
                    relato["http_status_validacao"] = resposta_consulta.status
                    relato["url_validacao"] = "https://rastreamento.correios.com.br/app/resultado.php"
                    if not resposta_consulta.ok:
                        raise RuntimeError(f"Os Correios responderam HTTP {resposta_consulta.status}.")
                    dados = resposta_consulta.json()
                    if not isinstance(dados, dict):
                        raise RuntimeError("Os Correios retornaram um formato de resposta inesperado.")
                    mensagem = str(dados.get("mensagem") or "")
                    relato["resposta_servidor"] = {"erro": bool(dados.get("erro")), "mensagem": mensagem,
                                                  "codigo_retornado": dados.get("codObjeto")}
                    if "captcha" in mensagem.casefold():
                        leitura["aceita_pelo_servidor"] = False
                        print("Os Correios recusaram a leitura do CAPTCHA.")
                        relato["resultado"] = "captcha_nao_aceito"
                        codigo_saida = 1
                        if tentativa < 3:
                            page.wait_for_function("anterior => document.querySelector('#captcha_image').getAttribute('src') !== anterior", arg=src_anterior)
                        continue
                    if dados.get("erro"):
                        relato["resultado"] = "consulta_sem_rastreamento"
                        relato["mensagem_correios"] = mensagem or "Consulta não concluída pelos Correios."
                        print("Resposta dos Correios: " + relato["mensagem_correios"])
                        codigo_saida = 1
                        break
                    resumo = resumir_rastreamento(dados, objeto)
                    leitura["aceita_pelo_servidor"] = True
                    relato.update({"resultado": "consulta_confirmada", "consulta_confirmada": True,
                                   "captcha_validado_pelo_servidor": True, "rastreamento": resumo})
                    print("\nRASTREAMENTO DO OBJETO")
                    for chave, titulo in (("codigo", "Código"), ("situacao", "Situação"),
                                          ("ultimo_local_informado", "Último local informado"), ("em_transito_para", "Em trânsito para"),
                                          ("ultima_atualizacao", "Atualizado em"), ("previsao_entrega", "Previsão informada pelos Correios"),
                                          ("observacao_previsao", "Observação da previsão")):
                        if resumo[chave]:
                            print(f"{titulo}: {resumo[chave]}")
                    codigo_saida = 0
                    break
                if args.manter_aberto:
                    print("\nO Chrome permanece na mesma sessão da imagem lida.")
                    input("Pressione ENTER aqui quando quiser fechar essa janela e voltar ao menu. ")
            finally:
                browser.close()
    except (Exception, KeyboardInterrupt) as exc:
        relato["erro"] = str(exc) or "Execução interrompida."
    if args.json_stdout:
        print("RELATORIO_JSON:" + json.dumps(relato, ensure_ascii=False, separators=(",", ":")), flush=True)
    if relato["consulta_confirmada"]:
        print("DEU CERTO! Os Correios confirmaram a consulta deste objeto.")
    elif relato["resultado"] == "leitura_realizada_sem_consulta":
        print("LEITURA CONCLUÍDA. O texto foi mostrado no CMD. Ainda não houve consulta para validar o CAPTCHA.")
    else:
        print("CONSULTA NÃO CONCLUÍDA. " + str(relato.get("erro") or relato.get("mensagem_correios") or "O CAPTCHA não foi aceito."))
    return codigo_saida


if __name__ == "__main__":
    raise SystemExit(main())
