"""O teste de viabilidade nunca confunde o widget com uma consulta ao TJSP."""

import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import menu
from testar_cloudflare import checkbox_nodes, liberacao_observada, mensagem_resultado, tempo_espera, testar_pagina


def relato_liberado():
    return dict(resultado="widget_liberado_sem_consulta", formulario_carregado=True,
                widget_detectado=True, resposta_emitida=True, liberacao_automatica_observada=True,
                intervencao_humana=False, consulta_realizada=False, validacao_servidor_confirmada=False)


class CloudflareTests(unittest.TestCase):
    def test_http_200_e_token_isolados_nao_confirmam_o_teste(self):
        for report in ({"http_status": 200}, {"resposta_emitida": True},
                       {"validacao_servidor_confirmada": True},
                       {**relato_liberado(), "intervencao_humana": True},
                       {**relato_liberado(), "resultado": "erro_tecnico"}):
            with self.subTest(report=report):
                self.assertFalse(liberacao_observada(report))

    def test_liberacao_do_widget_continua_sem_consulta_confirmada(self):
        report = relato_liberado()
        self.assertTrue(liberacao_observada(report))
        self.assertFalse(report["validacao_servidor_confirmada"])
        self.assertIn("ainda não foram testadas", mensagem_resultado(report))

    def test_formulario_com_token_encerra_sem_enviar_consulta(self):
        page = Mock()
        page.goto.return_value.status = 200
        page.goto.return_value.ok = True
        report = dict(consulta_realizada=False, validacao_servidor_confirmada=False)
        with patch("testar_cloudflare.ler_estado", return_value=dict(
            formulario_carregado=True, widget_detectado=True, resposta_emitida=True,
        )), patch("testar_cloudflare.acionar_caixa") as interact:
            self.assertEqual(testar_pagina(page, report, espera=5, etapa=Mock()), 0)
        interact.assert_not_called()
        page.locator.assert_not_called()
        page.keyboard.press.assert_not_called()
        self.assertFalse(report["consulta_realizada"])
        self.assertFalse(report["validacao_servidor_confirmada"])

    def test_indisponibilidade_nao_aciona_desafio(self):
        page = Mock()
        page.goto.return_value.status = 503
        page.goto.return_value.ok = False
        report = {}
        with patch("testar_cloudflare.acionar_caixa") as interact:
            self.assertEqual(testar_pagina(page, report, espera=5, etapa=Mock()), 2)
        interact.assert_not_called()
        self.assertEqual(report["resultado"], "pagina_indisponivel")

    def test_espera_limitada_nao_confirma_timeout(self):
        page = Mock()
        report = dict(formulario_carregado=True, widget_detectado=True, resposta_emitida=False)
        self.assertEqual(testar_pagina(page, report, espera=0, etapa=Mock()), 1)
        self.assertEqual(report["resultado"], "nao_liberou_no_prazo")
        self.assertFalse(liberacao_observada(report))

    def test_caixa_fechada_e_localizada_sem_selecionar_campos_de_texto(self):
        tree = {"shadowRoots": [{"children": [
            {"nodeName": "INPUT", "nodeId": 1, "attributes": ["type", "text"]},
            {"nodeName": "INPUT", "nodeId": 2, "attributes": ["type", "checkbox", "disabled", ""]},
            {"nodeName": "INPUT", "nodeId": 3, "attributes": ["type", "checkbox"]},
        ]}]}
        self.assertEqual(list(checkbox_nodes(tree)), [3])

    def test_menu_3_chama_tjsp_sem_modelo_de_audio(self):
        with patch("testar_cloudflare.main", return_value=0) as run:
            self.assertEqual(menu.main(["--tipo", "3", "--navegador", "msedge"]), 0)
            run.assert_called_once_with(["--navegador", "msedge"])

    def test_espera_tem_limite(self):
        for value in ("0", "121"):
            with self.assertRaises(argparse.ArgumentTypeError):
                tempo_espera(value)
        self.assertEqual(tempo_espera("60"), 60)


if __name__ == "__main__":
    unittest.main()
