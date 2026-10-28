"""A API não confirma um resultado incompleto nem executa consultas em paralelo."""

import csv
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_demo.app import classify_report, create_app


class WebDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(state_dir=self.temp.name)
        self.app.testing = True
        self.client = self.app.test_client()
        self.jobs = self.app.extensions["jobs"]

    def tearDown(self):
        self.temp.cleanup()

    def test_checkbox_e_token_sozinhos_nao_confirmam_verificacao(self):
        ok, _ = classify_report("recaptcha", {"checkbox_marcado": True, "resposta_emitida": True,
                                               "validacao_servidor_confirmada": False})
        self.assertFalse(ok)

    def test_cloudflare_nao_usa_confirmacao_do_google(self):
        ok, message = classify_report("cloudflare", {"validacao_servidor_confirmada": True})
        self.assertFalse(ok)
        self.assertIn("Cloudflare", message)

    def test_trf3_valida_cnpj_antes_de_iniciar(self):
        with patch("web_demo.app.threading.Thread.start") as start:
            invalid = self.client.post("/api/jobs", json={"kind": "trf3", "code": "07436109000116"})
            self.assertEqual(invalid.status_code, 400)
            start.assert_not_called()
            valid = self.client.post("/api/jobs", json={"kind": "trf3", "code": "07.436.109/0001-15"})
            self.assertEqual(valid.status_code, 202)
            self.assertEqual(valid.json["code"], "07436109000115")
            start.assert_called_once()

    def test_trf3_cnpj_divergente_nao_ganha_mensagem_de_sucesso(self):
        ok, message = classify_report("trf3", {"cnpj_consultado": "11111111111111"}, "07436109000115")
        self.assertFalse(ok)
        self.assertIn("não corresponde", message)

    def test_stj_exige_nome_e_preserva_entrada_editavel(self):
        with patch("web_demo.app.threading.Thread.start") as start:
            invalid = self.client.post("/api/jobs", json={"kind": "stj", "code": "07.436.109/0001-15"})
            self.assertEqual(invalid.status_code, 400)
            start.assert_not_called()
            valid = self.client.post("/api/jobs", json={"kind": "stj", "code": " Outra Empresa Ltda "})
            self.assertEqual(valid.status_code, 202)
            self.assertEqual(valid.json["code"], "OUTRA EMPRESA LTDA")
            start.assert_called_once()

    def test_stj_nome_divergente_nao_ganha_mensagem_de_sucesso(self):
        ok, message = classify_report("stj", {"nome_consultado": "OUTRA EMPRESA"}, "EMPRESA SOLICITADA")
        self.assertFalse(ok)
        self.assertIn("não corresponde", message)

    def test_cloudflare_aceita_teste_sem_numero_de_processo(self):
        with patch("web_demo.app.threading.Thread.start"):
            response = self.client.post("/api/jobs", json={"kind": "cloudflare"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["kind"], "cloudflare")
        self.assertEqual(response.json["code"], "")
        self.assertIn("cloudflare", self.client.get("/api/health").json["kinds"])

    def test_cloudflare_servir_captura_e_impedir_travessia(self):
        root = Path(self.temp.name) / "projeto"
        evidence = root / "evidencias_cloudflare" / "execucao"
        evidence.mkdir(parents=True)
        (evidence / "frame-001.png").write_bytes(b"captura-cloudflare")
        self.jobs.items["tjsp"] = {"_evidence": str(evidence)}
        with patch("web_demo.app.ROOT", root):
            response = self.client.get("/api/jobs/tjsp/artifacts/frame-001.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"captura-cloudflare")
            response.close()
            self.assertIsNone(self.jobs.artifact("tjsp", "../testar_cloudflare.py"))

    def test_objeto_divergente_nao_e_classificado_como_sucesso(self):
        report = {"consulta_confirmada": True, "captcha_validado_pelo_servidor": True,
                  "rastreamento": {"codigo": "BB123456785BR"}}
        self.assertFalse(classify_report("rastreamento", report, "AA123456785BR")[0])

    def test_entrada_invalida_e_origem_externa_nao_iniciam_trabalho(self):
        with patch("web_demo.app.threading.Thread.start") as start:
            invalid = self.client.post("/api/jobs", json={"kind": "rastreamento", "code": "00000000000"})
            self.assertEqual(invalid.status_code, 400)
            external = self.client.post("/api/jobs", json={"kind": "letras"}, headers={"Origin": "https://externo.invalid"})
            self.assertEqual(external.status_code, 403)
            start.assert_not_called()

    def test_segunda_consulta_e_rejeitada_ate_concluir_a_primeira(self):
        with patch("web_demo.app.threading.Thread.start") as start:
            first = self.client.post("/api/jobs", json={"kind": "letras"})
            second = self.client.post("/api/jobs", json={"kind": "recaptcha"})
            self.assertEqual(first.status_code, 202)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(second.json["active"], first.json["id"])
            self.assertEqual(start.call_count, 1)

    def test_exportacao_csv_preserva_campos_e_trata_formula_como_texto(self):
        report = {"codigo": "AA123456785BR", "situacao": "=texto do site", "ultimo_local_informado": "Campinas / SP",
                  "previsao_entrega": "Não informada pelos Correios"}
        self.jobs.items["teste"] = {"id": "teste", "kind": "rastreamento", "status": "concluido", "result": {"rastreamento": report}}
        response = self.client.get("/api/jobs/teste/report.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.data.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(rows[1][0], report["codigo"])
        self.assertEqual(rows[1][1], "'=texto do site")
        self.assertIn("Não informada", rows[1][5])

    def test_api_nao_expoe_caminhos_internos_ou_arquivos_arbitrarios(self):
        self.jobs.items["teste"] = {"id": "teste", "kind": "letras", "status": "concluido", "_evidence": "C:/fora",
                                   "_log": ["interno"], "created_at": "2026-10-26T10:00:00+00:00"}
        response = self.client.get("/api/jobs/teste")
        self.assertNotIn("_evidence", response.json)
        self.assertNotIn("_log", response.json)
        self.assertEqual(self.client.get("/api/jobs/teste/artifacts/app.py").status_code, 404)
        self.assertEqual(self.client.get("/api/jobs/teste/artifacts/resultado.json").status_code, 404)

    def test_captura_da_execucao_ativa_e_servida_sem_cache(self):
        root = Path(self.temp.name) / "projeto"
        evidence = root / "evidencias_correios" / "execucao"
        evidence.mkdir(parents=True)
        (evidence / "frame-001.png").write_bytes(b"imagem-desta-execucao")
        self.jobs.items["ao-vivo"] = {"_evidence": str(evidence)}
        with patch("web_demo.app.ROOT", root):
            response = self.client.get("/api/jobs/ao-vivo/artifacts/frame-001.png")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"imagem-desta-execucao")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            response.close()
            self.assertEqual(self.client.get("/api/jobs/ao-vivo/artifacts/frame-999.png").status_code, 404)


if __name__ == "__main__":
    unittest.main()
