"""Confere a identidade da pesquisa e não transforma falhas em ausência de processos."""

from pathlib import Path
from contextlib import contextmanager
import json
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import menu
import consultar_stj
from consultar_stj import (URL, aguardar_formulario, consulta_confirmada, extrair_processos, mensagem_resultado,
                           nome_no_resultado, normalizar_nome, pedido_da_pesquisa, total_exibido)

NOME = "EMPRESA DE TESTE LTDA"
TEXTO = """Listando processos relacionados a(s) parte(s) com nome EMPRESA DE TESTE LTDA.
Pesquisa resultou em 2 registro(s)!
Processo / UF Num. Registro Autuação Tipo Detalhes
AREsp 1234567/SP 2026/0123456-7 27/10/2026 Eletrônico
AGRAVANTE:EMPRESA DE TESTE LTDA
AGRAVADO:OUTRA PARTE
CC 123456/DF 2025/0234567-8 01/10/2025 Eletrônico
SUSCITANTE:EMPRESA DE TESTE LTDA
SUSCITADO:OUTRO TRIBUNAL
Versão 3.7.28.2
Contato: texto de rodapé
"""


def confirmado():
    return dict(resultado="consulta_concluida", consulta_confirmada=True,
                resposta_pesquisa_recebida=True, http_status_consulta=200,
                nome_formulario_confirmado=True, nome_resultado_confirmado=True,
                nome_consultado=NOME, nome_enviado=NOME, criterio="contem",
                coleta_completa=True, total_encontrados=2, processos=extrair_processos(TEXTO))


class StjTests(unittest.TestCase):
    def test_nome_editavel_nao_e_convertido_de_cnpj(self):
        self.assertEqual(normalizar_nome("  Empresa de\nTeste Ltda "), NOME)
        self.assertEqual(normalizar_nome("João & Filhos S.A."), "JOÃO & FILHOS S.A.")
        for value in (None, "", "07.436.109/0001-15", "a", "A" * 161):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalizar_nome(value)

    def test_lista_preserva_registro_partes_e_autuacao_sem_inventar_andamento(self):
        rows = extrair_processos(TEXTO)
        self.assertEqual(total_exibido(TEXTO), 2)
        self.assertIsNone(total_exibido("Verificação automática em andamento."))
        self.assertEqual(total_exibido("Pesquisa resultou em 0 registro(s)!"), 0)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["numero"], "AREsp 1234567/SP")
        self.assertEqual(rows[1]["autuacao"], "01/10/2025")
        self.assertNotIn("Contato", rows[1]["partes"])
        self.assertNotIn("ultima_movimentacao", rows[0])
        self.assertTrue(nome_no_resultado(TEXTO, NOME))
        self.assertFalse(nome_no_resultado(TEXTO, "OUTRA EMPRESA"))

    def test_token_http_200_ou_lista_parcial_nao_bastam(self):
        good = confirmado()
        self.assertTrue(consulta_confirmada(good, NOME))
        for changes in ({"nome_enviado": "OUTRA EMPRESA"}, {"nome_resultado_confirmado": False},
                        {"total_encontrados": 3}, {"coleta_completa": False},
                        {"resposta_pesquisa_recebida": False}, {"http_status_consulta": 403},
                        {"processos": [None, None]}, {"resultado": "falha_rede"}):
            self.assertFalse(consulta_confirmada({**good, **changes}, NOME))
        self.assertFalse(consulta_confirmada({"resposta_emitida": True, "http_status_consulta": 200}, NOME))
        self.assertIn("não confirma o vínculo", mensagem_resultado(good))

    def test_lista_de_nomes_nao_e_lista_de_processos(self):
        texto = f"Listando parte(s) com nome {NOME}.\nPesquisa resultou em 3 registro(s)!"
        self.assertTrue(consultar_stj.selecao_de_partes(texto, NOME))
        self.assertFalse(consultar_stj.selecao_de_partes(texto, "OUTRA EMPRESA"))
        self.assertFalse(nome_no_resultado(texto, NOME))
        self.assertFalse(consultar_stj.selecao_de_partes(TEXTO, NOME))
        report = dict(resultado="selecao_parte_pendente", total_nomes_encontrados=3)
        self.assertFalse(consulta_confirmada(report))
        self.assertIn("nomes semelhantes", mensagem_resultado(report))

    def test_requisicao_exige_nome_criterio_acao_e_destino_corretos(self):
        fields = dict(parteNome=NOME, aplicacao="processos.ea", opcoesFoneticaPhonosParte="2",
                      acao="pushconsultarprocessoconsultalimitenaoatendidasjaincluidas")
        request = Mock(url=URL, method="POST", post_data=urlencode(fields))
        self.assertTrue(pedido_da_pesquisa(request, NOME))
        self.assertFalse(pedido_da_pesquisa(request, "OUTRA EMPRESA"))
        request.post_data = urlencode({**fields, "opcoesFoneticaPhonosParte": "1"})
        self.assertFalse(pedido_da_pesquisa(request, NOME))
        request.post_data = urlencode(fields)
        request.url = "https://outro.invalid/processo/pesquisa/"
        self.assertFalse(pedido_da_pesquisa(request, NOME))

    def test_menu_5_preserva_nome_digitado(self):
        with patch("consultar_stj.main", return_value=0) as run:
            self.assertEqual(menu.main(["--tipo", "5", "--parte", NOME]), 0)
        run.assert_called_once_with(["--parte", NOME, "--navegador", "chrome"])

    def test_pagina_incompleta_recebe_uma_recarga_sem_enviar_pesquisa(self):
        for recupera in (True, False):
            with self.subTest(recupera=recupera):
                page = Mock()
                page.goto.return_value.status = 403
                campo, corpo = Mock(), Mock()
                page.locator.side_effect = lambda selector: corpo if selector == "body" else campo
                campo.is_visible.return_value = True
                corpo.inner_text.side_effect = lambda **kwargs: "Nome da PARTE" if recupera and page.goto.call_count == 2 else "{{cabecalhoErro}}"
                tempo = [0.0]
                page.wait_for_timeout.side_effect = lambda ms: tempo.__setitem__(0, tempo[0] + ms / 1000)
                report = {}
                with patch("consultar_stj.time.monotonic", side_effect=lambda: tempo[0]), \
                     patch("consultar_stj.frames_cloudflare", return_value=[]), \
                     patch("consultar_stj.capturar_etapa"):
                    self.assertEqual(aguardar_formulario(page, report, Path(".")), recupera)
                self.assertEqual(page.goto.call_count, 2)
                campo.click.assert_not_called()
                self.assertEqual(report["tentativas_abertura"][1]["aplicacao_inicializada"], recupera)
                if not recupera:
                    self.assertEqual(report["resultado"], "aplicacao_indisponivel")

    def test_verificacao_sem_iframe_aguarda_e_pode_recuperar(self):
        for recupera in (False, True):
            with self.subTest(recupera=recupera):
                page = Mock()
                page.goto.return_value.status = 200
                corpo, campo = Mock(), Mock()
                page.locator.side_effect = lambda selector: corpo if selector == "body" else campo
                tempo = [0.0]
                corpo.inner_text.side_effect = lambda **kw: (
                    "Nome da PARTE" if recupera and tempo[0] >= 2 else "Verificação automática em andamento.")
                campo.is_visible.return_value = True
                page.wait_for_timeout.side_effect = lambda ms: tempo.__setitem__(0, tempo[0] + ms / 1000)
                relato = {}
                with patch("consultar_stj.time.monotonic", side_effect=lambda: tempo[0]), \
                     patch("consultar_stj.frames_cloudflare", return_value=[]), \
                     patch("consultar_stj.capturar_etapa"), patch("builtins.print"):
                    self.assertEqual(aguardar_formulario(page, relato, Path(".")), recupera)
                self.assertEqual(page.goto.call_count, 1)
                self.assertTrue(relato["verificacao_acesso_observada"])
                campo.fill.assert_not_called()
                if not recupera:
                    self.assertEqual(relato["resultado"], "verificacao_pendente")
                    self.assertEqual(tempo[0], 120)
                    self.assertFalse(consulta_confirmada(relato))

    def test_leitura_durante_redirecionamento_e_timeout_pode_repetir(self):
        page = Mock()
        for exc in (PlaywrightTimeoutError("body ausente"),
                    PlaywrightError("Execution context was destroyed")):
            page.locator.return_value.inner_text.side_effect = exc
            self.assertIsNone(consultar_stj.ler_corpo(page))
        page.locator.return_value.inner_text.side_effect = PlaywrightError("Target page has been closed")
        with self.assertRaises(PlaywrightError):
            consultar_stj.ler_corpo(page)

    def test_falha_no_fechamento_preserva_verificacao_pendente(self):
        @contextmanager
        def browser(*args, **kwargs):
            yield Mock()
            raise subprocess.TimeoutExpired("browser", 10)

        def pesquisa(page, nome, relato, pasta):
            relato["resultado"] = "verificacao_pendente"
            return 1

        with tempfile.TemporaryDirectory() as temp, patch("consultar_stj.ROOT", Path(temp)), \
             patch("consultar_stj.sync_playwright"), patch("consultar_stj.abrir_pagina", browser), \
             patch("consultar_stj.pesquisar", side_effect=pesquisa), patch("builtins.print"):
            self.assertEqual(consultar_stj.main(["--parte", NOME]), 2)
            relato = json.loads(next(Path(temp).glob("evidencias_stj/*/resultado.json")).read_text(encoding="utf-8"))
        self.assertEqual(relato["resultado"], "verificacao_pendente")
        self.assertEqual(relato["erro_encerramento_tipo"], "TimeoutExpired")
        self.assertFalse(consulta_confirmada(relato))


if __name__ == "__main__":
    unittest.main()
