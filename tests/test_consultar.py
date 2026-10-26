"""Verificações com Edge real e página fictícia, sem resolver CAPTCHAs externos."""

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from consultar import (ConsultaError, aguardar_resultado, config_demo, consultar_pagina,
                       executar_consulta, salvar_resultado, validar_config)
from playwright.sync_api import sync_playwright


class FluxoLocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(channel="msedge", headless=True)
        except Exception:
            cls.playwright.stop()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(locale="pt-BR")
        self.page = self.context.new_page()
        self.page.set_default_timeout(1500)
        self.config = config_demo()

    def tearDown(self):
        self.context.close()

    def test_consulta_exporta_o_documento_consultado_sem_sobrescrever(self):
        chamadas = []

        def operador(prompt):
            chamadas.append(prompt)
            if len(chamadas) == 2:
                self.assertEqual(self.page.locator("#documento").input_value(), "DEMO-456")
                self.page.locator("#confirmacao").fill("TESTE")
            return ""

        dados = consultar_pagina(self.page, self.config, {"documento": "DEMO-456"}, operador)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(dados, {"documento": "DEMO-456", "nome": "Empresa de demonstração", "situacao": "DADO FICTÍCIO"})
        with tempfile.TemporaryDirectory() as temp:
            destino = Path(temp)
            primeira = salvar_resultado(destino, self.config, {"documento": "DEMO-456"}, dados, demo=True)
            original = (primeira / "resultado.json").read_bytes()
            segunda = salvar_resultado(destino, self.config, {"documento": "DEMO-789"}, dados, demo=True)
            self.assertNotEqual(primeira, segunda)
            self.assertEqual(original, (primeira / "resultado.json").read_bytes())
            payload = json.loads(original)
            self.assertEqual(payload["modo"], "demonstracao")
            self.assertEqual(payload["resultado"]["documento"], "DEMO-456")
            with (primeira / "resultado.csv").open(encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle, delimiter=";")), [dados])

    def test_etapa_manual_incompleta_retorna_erro_do_site(self):
        with self.assertRaisesRegex(ConsultaError, "Etapa manual não confirmada"):
            consultar_pagina(self.page, self.config, {"documento": "DEMO-001"}, lambda _: "")

    def test_espera_por_resultado_ausente_nao_retorna_dados(self):
        self.page.goto(self.config["url"])
        self.config["timeout_segundos"] = 1
        with self.assertRaisesRegex(ConsultaError, "resultado não apareceu"):
            aguardar_resultado(self.page, self.config)

    def test_campo_vazio_nao_e_resultado_confirmado(self):
        self.page.goto(self.config["url"])
        self.page.locator("#documento").fill("DEMO-001")
        self.page.locator("#confirmacao").fill("TESTE")
        self.page.locator("#consultar").click()
        self.page.locator("#nome").evaluate("element => element.textContent = ''")
        with self.assertRaisesRegex(ConsultaError, "'nome' ficou vazio"):
            aguardar_resultado(self.page, self.config)


class EntradaESaidaTests(unittest.TestCase):
    def test_config_exemplo_nao_consulta_endereco_ficticio(self):
        arquivo = Path(__file__).resolve().parents[1] / "config.exemplo.json"
        with self.assertRaisesRegex(ConsultaError, "URL de exemplo"):
            validar_config(json.loads(arquivo.read_text(encoding="utf-8")))

    def test_entrada_incompleta_ou_desconhecida_nao_abre_navegador(self):
        for valores in ({}, {"documento": ""}, {"documento": "123", "errado": "456"}):
            with self.subTest(valores=valores), self.assertRaises(ConsultaError):
                executar_consulta(config_demo(), valores, permitir_demo=True)

    def test_texto_de_resultado_nao_vira_formula_no_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            pasta = salvar_resultado(Path(temp), config_demo(), {}, {"nome": '=HYPERLINK("exemplo")'}, demo=True)
            with (pasta / "resultado.csv").open(encoding="utf-8-sig", newline="") as handle:
                linhas = list(csv.reader(handle, delimiter=";"))
            self.assertTrue(linhas[1][0].startswith("'="))
            payload = json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["resultado"]["nome"], '=HYPERLINK("exemplo")')


if __name__ == "__main__":
    unittest.main()
