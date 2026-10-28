"""Identidade do CNPJ e completude da consulta pública, sem acessar o tribunal."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import menu
from consultar_trf3 import (DOCUMENTO, URL, consulta_confirmada, extrair_linhas, formatar_cnpj,
                           mensagem_resultado, normalizar_cnpj, pedido_da_pesquisa, total_exibido)

CNPJ = "07436109000115"
PROCESSO = "5002803-24.2025.4.03.6126"


def confirmado(total=1):
    return dict(resultado="consulta_concluida", consulta_confirmada=True,
                resposta_pesquisa_recebida=True, http_status_consulta=200,
                cnpj_formulario_confirmado=True, cnpj_consultado=CNPJ, cnpj_enviado=CNPJ,
                coleta_completa=True, total_encontrados=total,
                processos=[{"numero": PROCESSO}] if total else [])


class Trf3Tests(unittest.TestCase):
    def test_cnpj_preserva_zero_inicial_e_confere_digitos(self):
        self.assertEqual(normalizar_cnpj("07.436.109/0001-15"), CNPJ)
        self.assertEqual(formatar_cnpj(CNPJ), "07.436.109/0001-15")
        for value in ("07436109000116", "00000000000000", "7436109000115", "07436109000115x", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalizar_cnpj(value)

    def test_contador_inicial_nao_e_consulta_vazia(self):
        self.assertIsNone(total_exibido("resultados encontrados"))
        self.assertEqual(total_exibido("0 resultados encontrados"), 0)
        self.assertEqual(total_exibido("1.234 resultados encontrados"), 1234)

    def test_dados_sao_extraidos_da_linha_sem_concluir_situacao_juridica(self):
        rows = [["Ver detalhes", f"PROCEDIMENTO COMUM CÍVEL\nProceComCiv {PROCESSO} - Assunto de teste\nAUTOR X EMPRESA",
                 "Publicado Intimação em 27/10/2026. (27/10/2026 01:28:39)"]]
        result = extrair_linhas(rows + rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["numero"], PROCESSO)
        self.assertEqual(result[0]["classe"], "PROCEDIMENTO COMUM CÍVEL")
        self.assertEqual(result[0]["partes"], "AUTOR X EMPRESA")
        self.assertEqual(result[0]["data_ultima_movimentacao"], "27/10/2026 01:28:39")
        self.assertNotIn("situacao", result[0])

    def test_resposta_parcial_ou_outro_cnpj_nao_confirma(self):
        good = confirmado()
        self.assertTrue(consulta_confirmada(good, CNPJ))
        for report in ({"http_status_consulta": 200}, {**good, "cnpj_enviado": "11111111111111"},
                       {**good, "total_encontrados": 2}, {**good, "coleta_completa": False},
                       {**good, "processos": [{"numero": 123}]}, {**good, "resultado": "falha_rede"}):
            with self.subTest(report=report):
                self.assertFalse(consulta_confirmada(report, CNPJ))
        self.assertFalse(consulta_confirmada(good, "11111111111111"))

    def test_zero_confirmado_nao_afirma_inexistencia_de_processos(self):
        report = confirmado(0)
        self.assertTrue(consulta_confirmada(report))
        self.assertIn("não comprova inexistência", mensagem_resultado(report))

    def test_pedido_da_pesquisa_exige_destino_e_cnpj_exatos(self):
        request = Mock(url=URL + ";jsessionid2=teste", method="POST",
                       post_data=urlencode({DOCUMENTO: "07.436.109/0001-15", "fPP:j_id247": "fPP:j_id247",
                                            "fPP": "fPP", "AJAXREQUEST": "_viewRoot", "javax.faces.ViewState": "teste"}))
        self.assertTrue(pedido_da_pesquisa(request, CNPJ))
        self.assertFalse(pedido_da_pesquisa(request, "11111111111111"))
        request.url = "https://outro.invalid/pje/ConsultaPublica/listView.seam"
        self.assertFalse(pedido_da_pesquisa(request, CNPJ))
        request.url = URL
        request.post_data = urlencode({DOCUMENTO: "07.436.109/0001-15", "fPP": "fPP"})
        self.assertFalse(pedido_da_pesquisa(request, CNPJ))

    def test_opcao_4_usa_o_cnpj_informado(self):
        with patch("consultar_trf3.main", return_value=0) as run:
            self.assertEqual(menu.main(["--tipo", "4", "--cnpj", CNPJ]), 0)
        run.assert_called_once_with(["--cnpj", CNPJ, "--navegador", "chrome"])


if __name__ == "__main__":
    unittest.main()
