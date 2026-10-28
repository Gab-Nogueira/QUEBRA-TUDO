"""Confere a identidade da pesquisa e não transforma falhas em ausência de processos."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import menu
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
                corpo.inner_text.side_effect = lambda: "Nome da PARTE" if recupera and page.goto.call_count == 2 else "{{cabecalhoErro}}"
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


if __name__ == "__main__":
    unittest.main()
