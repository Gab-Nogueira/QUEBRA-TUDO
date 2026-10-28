"""A API não confirma um resultado incompleto nem executa consultas em paralelo."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from consulta_assistida.web_demo.app import classify_report, create_app


class WebDemoTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self.jobs = self.app.extensions["jobs"]

    def test_checkbox_e_token_sozinhos_nao_confirmam_verificacao(self):
        ok, _ = classify_report("recaptcha", {"checkbox_marcado": True, "resposta_emitida": True,
                                               "validacao_servidor_confirmada": False})
        self.assertFalse(ok)

    def test_objeto_divergente_nao_e_classificado_como_sucesso(self):
        report = {"consulta_confirmada": True, "captcha_validado_pelo_servidor": True,
                  "rastreamento": {"codigo": "BB123456785BR"}}
        self.assertFalse(classify_report("rastreamento", report, "AA123456785BR")[0])

    def test_entrada_invalida_e_origem_externa_nao_iniciam_trabalho(self):
        with patch("consulta_assistida.web_demo.app.threading.Thread.start") as start:
            invalid = self.client.post("/api/jobs", json={"kind": "rastreamento", "code": "00000000000"})
            self.assertEqual(invalid.status_code, 400)
            external = self.client.post("/api/jobs", json={"kind": "letras"}, headers={"Origin": "https://externo.invalid"})
            self.assertEqual(external.status_code, 403)
            start.assert_not_called()

    def test_segunda_consulta_e_rejeitada_ate_concluir_a_primeira(self):
        with patch("consulta_assistida.web_demo.app.threading.Thread.start") as start:
            first = self.client.post("/api/jobs", json={"kind": "letras"})
            second = self.client.post("/api/jobs", json={"kind": "recaptcha"})
            self.assertEqual(first.status_code, 202)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(second.json["active"], first.json["id"])
            self.assertEqual(start.call_count, 1)

    def test_resultado_fica_em_memoria_sem_rota_de_exportacao(self):
        report = {"codigo": "AA123456785BR", "situacao": "Em tr?nsito"}
        self.jobs.items["teste"] = {"id": "teste", "kind": "rastreamento", "status": "concluido",
                                     "result": {"rastreamento": report}, "created_at": "2026-10-26T10:00:00+00:00"}
        response = self.client.get("/api/jobs/teste")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["result"]["rastreamento"], report)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(self.client.get("/api/jobs/teste/report.csv").status_code, 404)

    def test_api_nao_expoe_caminhos_internos_ou_arquivos_arbitrarios(self):
        self.jobs.items["teste"] = {"id": "teste", "kind": "letras", "status": "concluido", "_evidence": "C:/fora",
                                   "_log": ["interno"], "created_at": "2026-10-26T10:00:00+00:00"}
        response = self.client.get("/api/jobs/teste")
        self.assertNotIn("_evidence", response.json)
        self.assertNotIn("_log", response.json)
        self.assertEqual(self.client.get("/api/jobs/teste/artifacts/app.py").status_code, 404)
        self.assertEqual(self.client.get("/api/jobs/teste/artifacts/resultado.json").status_code, 404)

    def test_interface_nao_cria_historico_ou_arquivos_de_evidencia(self):
        response = self.client.get("/api/jobs/inexistente/artifacts/frame-001.png")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
