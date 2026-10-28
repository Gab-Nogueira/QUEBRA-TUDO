"""Conferência do objeto e dos dados de entrega, sem consultas externas."""

from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rastreamento_correios import normalizar_objeto, resumir_rastreamento


class RastreamentoTests(unittest.TestCase):
    def setUp(self):
        self.codigo = "AA123456785BR"
        self.retorno = {
            "codObjeto": self.codigo,
            "dtPrevista": "30/10/2026",
            "eventos": [
                {"dtHrCriado": {"date": "2026-10-20 10:00:00"}, "descricao": "Objeto postado",
                 "unidade": {"tipo": "Agência", "endereco": {"cidade": "Campinas", "uf": "SP"}}},
                {"dtHrCriado": {"date": "2026-10-25 15:00:00"}, "descricao": "Objeto em transferência",
                 "unidade": {"tipo": "Centro de distribuição", "endereco": {"cidade": "São Paulo", "uf": "SP"}},
                 "unidadeDestino": {"tipo": "Centro de distribuição", "endereco": {"cidade": "Curitiba", "uf": "PR"}}},
            ],
        }

    def test_ultimo_evento_e_destino_sao_identificados_sem_assumir_que_ja_chegou(self):
        resumo = resumir_rastreamento(self.retorno, self.codigo, hoje=date(2026, 10, 26))
        self.assertEqual(resumo["situacao"], "Objeto em transferência")
        self.assertIn("São Paulo / SP", resumo["ultimo_local_informado"])
        self.assertIn("Curitiba / PR", resumo["em_transito_para"])
        self.assertEqual(resumo["previsao_entrega"], "30/10/2026")
        self.assertIsNone(resumo["observacao_previsao"])

    def test_objeto_diferente_ou_sem_eventos_nao_e_consulta_confirmada(self):
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            resumir_rastreamento(self.retorno, "BB123456785BR")
        self.retorno["eventos"] = []
        with self.assertRaisesRegex(ValueError, "não retornaram eventos"):
            resumir_rastreamento(self.retorno, self.codigo)

    def test_previsao_ausente_nao_e_inventada_e_previsao_antiga_e_sinalizada(self):
        self.retorno.pop("dtPrevista")
        resumo = resumir_rastreamento(self.retorno, self.codigo, hoje=date(2026, 10, 26))
        self.assertEqual(resumo["previsao_entrega"], "Não informada pelos Correios")
        self.retorno["dtPrevista"] = "19/06/2024"
        resumo = resumir_rastreamento(self.retorno, self.codigo, hoje=date(2026, 10, 26))
        self.assertIn("já passou", resumo["observacao_previsao"])

    def test_cpf_e_codigo_incompleto_nao_disparam_consulta_de_objeto(self):
        self.assertEqual(normalizar_objeto("aa 123456785 br"), self.codigo)
        self.assertEqual(normalizar_objeto(""), "")
        for valor in ("00000000000", "12345678901234", "AA123BR"):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                normalizar_objeto(valor)


if __name__ == "__main__":
    unittest.main()
