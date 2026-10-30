"""Regressões da revisão: falhas não bloqueiam a fila nem confirmam resultados."""

from io import StringIO
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_demo.app import Jobs, classify_report, create_app
from web_demo import launch
from web_demo.runtime import state_directory
import consultar_stj


def google_report():
    return dict(resultado="aprovado_na_demonstracao", validacao_servidor_confirmada=True,
                http_status_validacao=200, intervencao_humana=False)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch("web_demo.app.get_proofs", return_value={}).start()
        self.app = create_app(state_dir=self.temp.name)
        self.app.testing = True
        self.client = self.app.test_client()
        self.jobs = self.app.extensions["jobs"]

    def test_tipo_json_invalido_retorna_400_sem_abrir_processo(self):
        with patch("web_demo.app.threading.Thread.start") as start:
            for value in ([], {}, None, 1, True, "desconhecido"):
                with self.subTest(value=value):
                    self.assertEqual(self.client.post("/api/jobs", json={"kind": value}).status_code, 400)
            start.assert_not_called()

    def test_falha_ao_iniciar_thread_libera_fila_e_permite_nova_consulta(self):
        with patch("web_demo.app.threading.Thread.start", side_effect=RuntimeError("simulado")), \
             patch.object(self.app.logger, "exception"):
            self.assertEqual(self.client.post("/api/jobs", json={"kind": "letras"}).status_code, 503)
        self.assertIsNone(self.jobs.active)
        self.assertEqual(next(iter(self.jobs.items.values()))["status"], "falhou")
        with patch("web_demo.app.threading.Thread.start"):
            self.assertEqual(self.client.post("/api/jobs", json={"kind": "letras"}).status_code, 202)

    def test_falha_de_gravacao_libera_fila(self):
        with patch.object(self.jobs, "save", side_effect=OSError("simulado")), \
             patch("web_demo.app.threading.Thread.start") as start, patch.object(self.app.logger, "exception"):
            self.assertEqual(self.client.post("/api/jobs", json={"kind": "letras"}).status_code, 503)
            start.assert_not_called()
        self.assertIsNone(self.jobs.active)

    def test_relatorio_incompleto_ou_booleano_em_texto_nao_confirma(self):
        good = google_report()
        self.assertTrue(classify_report("recaptcha", good)[0])
        for report in ([], None, {"validacao_servidor_confirmada": "false"},
                       {**good, "intervencao_humana": True}, {**good, "http_status_validacao": 403},
                       {**good, "resultado": "erro_tecnico"}):
            self.assertFalse(classify_report("recaptcha", report)[0])
        self.assertFalse(classify_report("rastreamento", {"rastreamento": None}, "AA123456785BR")[0])

    def test_correios_exige_retorno_do_servidor_e_codigo_solicitado(self):
        code = "AA123456785BR"
        good = dict(resultado="consulta_confirmada", consulta_confirmada=True,
                    captcha_validado_pelo_servidor=True, http_status_validacao=200,
                    codigo_consultado=code, rastreamento={"codigo": code},
                    resposta_servidor={"erro": False, "codigo_retornado": code})
        self.assertTrue(classify_report("rastreamento", good, code)[0])
        for field, value in (("consulta_confirmada", "false"), ("http_status_validacao", 500),
                             ("codigo_consultado", "BB123456785BR"), ("resposta_servidor", None)):
            self.assertFalse(classify_report("rastreamento", {**good, field: value}, code)[0])

    def test_saida_com_erro_nao_confirma_mesmo_com_relatorio_positivo(self):
        root = Path(self.temp.name) / "project"
        evidence = root / "evidencias_recaptcha" / "run"
        evidence.mkdir(parents=True)
        (evidence / "resultado.json").write_text(json.dumps(google_report()), encoding="utf-8")
        with patch("web_demo.app.threading.Thread.start"):
            job = self.jobs.start("recaptcha", "")
        process = Mock(stdout=StringIO(f"Evidências: {evidence}\n"))
        process.wait.return_value = 2
        with patch("web_demo.app.ROOT", root), patch("web_demo.app.subprocess.Popen", return_value=process):
            self.jobs.run(job["id"])
        final = self.client.get(f"/api/jobs/{job['id']}").json
        self.assertEqual(final["status"], "falhou")
        self.assertEqual(final["process_returncode"], 2)
        self.assertFalse(final["verified"])
        self.assertIsNone(self.jobs.active)

    def test_inicio_e_fim_sao_persistidos_e_reinicio_interrompe_execucao(self):
        with patch("web_demo.app.threading.Thread.start"):
            started = self.jobs.start("letras", "")
        restarted = Jobs(Path(self.temp.name))
        self.assertIsNone(restarted.active)
        self.assertEqual(restarted.items[started["id"]]["status"], "falhou")

    def test_health_identifica_copia_revisao_e_configuracao_sem_caminhos(self):
        result = self.client.get("/api/health").json
        self.assertEqual(set(result["instance"]), {"project", "revision"})
        self.assertTrue(result["headless"])
        self.assertNotIn(str(Path(__file__).parent), json.dumps(result))

    def test_launcher_nao_reutiliza_outra_copia_revisao_ou_configuracao(self):
        expected = {"project": "atual", "revision": "nova"}
        good = dict(service="rastro-demo", ok=True, instance=expected, headless=True)
        self.assertTrue(launch.compatible(good, expected, True))
        for current in ({"service": "rastro-demo"}, {**good, "instance": {"project": "outra", "revision": "nova"}},
                        {**good, "instance": {"project": "atual", "revision": "antiga"}}, {**good, "headless": False}):
            with self.subTest(current=current), patch("web_demo.launch.health", return_value=current), \
                 patch("web_demo.launch.identity", return_value=expected), patch("web_demo.launch.subprocess.Popen") as start, \
                 patch("builtins.print"):
                self.assertEqual(launch.main([]), 1)
                start.assert_not_called()

    def test_launcher_nao_abre_segundo_processo_em_porta_ocupada(self):
        with patch("web_demo.launch.health", return_value=None), patch("web_demo.launch.port_available", return_value=False), \
             patch("web_demo.launch.subprocess.Popen") as start, patch("builtins.print"):
            self.assertEqual(launch.main([]), 1)
            start.assert_not_called()

    def test_launcher_abre_navegador_so_quando_solicitado_e_servico_compativel(self):
        expected = {"project": "atual", "revision": "nova"}
        current = dict(service="rastro-demo", ok=True, instance=expected, headless=True)
        with patch("web_demo.launch.identity", return_value=expected), \
             patch("web_demo.launch.health", return_value=current), \
             patch("web_demo.launch.socket.getaddrinfo", return_value=[]), \
             patch("web_demo.launch.webbrowser.open") as browser, patch("builtins.print"):
            self.assertEqual(launch.main(["--port", "5086"]), 0)
            browser.assert_not_called()
            self.assertEqual(launch.main(["--port", "5086", "--abrir"]), 0)
            browser.assert_called_once_with("http://localhost:5086")

    def test_launcher_nao_abre_navegador_se_porta_ocupada(self):
        with patch("web_demo.launch.health", return_value=None), \
             patch("web_demo.launch.port_available", return_value=False), \
             patch("web_demo.launch.webbrowser.open") as browser, patch("builtins.print"):
            self.assertEqual(launch.main(["--abrir"]), 1)
            browser.assert_not_called()

    def test_estados_de_copias_e_portas_diferentes_sao_separados(self):
        self.assertNotEqual(state_directory(5085, "copia1"), state_directory(5085, "copia2"))
        self.assertNotEqual(state_directory(5085, "copia1"), state_directory(5086, "copia1"))

    def test_leitura_sem_lista_de_textos_nao_confirma(self):
        for attempts in ({"texto": "abc"}, [None], [{"texto": ""}], ["abc"]):
            self.assertFalse(classify_report("letras", dict(resultado="leitura_realizada_sem_consulta", tentativas=attempts))[0])

    def test_historico_invalido_e_preservado_antes_de_recomecar(self):
        for raw in (b"[]", b'{"run":null}', b'{"truncado":', b'\xff'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temp:
                file = Path(temp) / "execucoes.json"
                file.write_bytes(raw)
                jobs = Jobs(Path(temp))
                self.assertEqual(jobs.items, {})
                jobs.save()
                self.assertEqual(json.loads(file.read_text()), {})
                self.assertEqual(next(Path(temp).glob("execucoes-invalido-*.json")).read_bytes(), raw)

    def test_stj_erro_ao_fechar_navegador_nao_retorna_codigo_zero(self):
        @contextmanager
        def browser(*args, **kwargs):
            yield Mock()
            raise RuntimeError("falha simulada no fechamento")

        with patch("consultar_stj.ROOT", Path(self.temp.name)), patch("consultar_stj.sync_playwright"), \
             patch("consultar_stj.abrir_pagina", browser), patch("consultar_stj.pesquisar", return_value=0), patch("builtins.print"):
            self.assertEqual(consultar_stj.main(["--parte", "EMPRESA DE TESTE"]), 2)
        report = json.loads(next(Path(self.temp.name).glob("evidencias_stj/*/resultado.json")).read_text(encoding="utf-8"))
        self.assertEqual(report["resultado"], "erro_tecnico")


if __name__ == "__main__":
    unittest.main()
