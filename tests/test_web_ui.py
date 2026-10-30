"""Interface real em Chrome, com API isolada e sem consultas externas."""

from pathlib import Path
import base64
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server, WSGIRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from web_demo.app import create_app


class SilentHandler(WSGIRequestHandler):
    def log_request(self, *args, **kwargs):
        pass


class WebUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        with patch("web_demo.app.get_proofs", return_value={}):
            cls.app = create_app(state_dir=cls.temp.name)
        cls.server = make_server("127.0.0.1", 0, cls.app, request_handler=SilentHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel="chrome", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def setUp(self):
        self.jobs = self.app.extensions["jobs"]
        self.jobs.active = None
        self.jobs.items.clear()
        self.context = self.browser.new_context(viewport={"width": 1366, "height": 900})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(f"http://127.0.0.1:{self.server.server_port}")
        self.page.wait_for_function("document.querySelector('#connection').textContent === 'Disponível'")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def test_cnpj_invalido_mostra_mensagem_e_libera_botoes(self):
        self.page.locator("#trf3-cnpj").fill("07436109000116")
        self.page.locator("#test-trf3").click()
        self.page.locator("#request-error").wait_for(state="visible")
        self.assertIn("verificadores", self.page.locator("#request-error").inner_text())
        self.assertTrue(self.page.locator("#test-stj").is_enabled())
        self.assertIsNone(self.jobs.active)

    def test_campo_editavel_nao_altera_consulta_em_andamento_e_falha_nao_confirma(self):
        with patch("web_demo.app.threading.Thread.start"):
            self.page.locator("#stj-parte").fill("Empresa de Teste Ltda")
            self.page.locator("#test-stj").click()
            self.page.wait_for_function("document.querySelector('#run-status').textContent === 'EM ANDAMENTO'")
        ident = self.jobs.active
        self.page.locator("#stj-parte").fill("Outra Empresa Ltda")
        self.assertEqual(self.jobs.items[ident]["code"], "EMPRESA DE TESTE LTDA")
        with self.jobs.lock:
            self.jobs.items[ident].update(status="falhou", message="Falha de rede simulada", result={"processos": [None]})
            self.jobs.active = None
        self.page.wait_for_function("document.querySelector('#run-status').textContent === 'NÃO CONFIRMADO'")
        self.assertEqual(self.page.locator("#stj-parte").input_value(), "Outra Empresa Ltda")
        self.assertIn("Falha de rede", self.page.locator("#result-content").inner_text())
        self.assertTrue(self.page.locator("#test-stj").is_enabled())

    def test_execucao_removida_nao_prende_interface_em_polling(self):
        with patch("web_demo.app.threading.Thread.start"):
            self.page.locator("#test-recaptcha").click()
            self.page.wait_for_function("document.querySelector('#run-status').textContent === 'EM ANDAMENTO'")
        with self.jobs.lock:
            self.jobs.items.clear()
            self.jobs.active = None
        self.page.locator("#request-error").wait_for(state="visible")
        self.assertIn("não está mais disponível", self.page.locator("#request-error").inner_text())
        self.assertTrue(self.page.locator("#test-recaptcha").is_enabled())
        self.assertTrue(self.page.locator("#empty-state").is_visible())

    def test_desktop_e_celular_sem_rolagem_horizontal(self):
        for width in (1366, 390, 320):
            self.page.set_viewport_size({"width": width, "height": 900})
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            self.assertEqual(self.page.locator("[data-test]").count(), 5)

    def test_tjsp_numero_ficticio_preservado_na_consulta(self):
        with patch("web_demo.app.threading.Thread.start"):
            self.page.locator("#tjsp-processo").fill("5364723-18.2024.8.26.0000")
            self.page.locator("#tjsp-processo").press("Enter")
            self.page.wait_for_function("document.querySelector('#run-status').textContent === 'EM ANDAMENTO'")
        self.assertEqual(self.page.locator("#tjsp-processo").input_value(), "5364723-18.2024.8.26.0000")
        self.assertEqual(self.jobs.items[self.jobs.active]['code'], '5364723-18.2024.8.26.0000')
        self.assertEqual(self.jobs.items[self.jobs.active]['instancia'], 'SP')
        self.assertEqual(self.page.locator('#tjsp-instancia').input_value(), 'SP')

    def test_tjsp_token_sem_pagina_nao_mostra_processo_aberto(self):
        self.page.route("**/artifacts/tela.png", lambda route: route.fulfill(status=404))
        job = dict(id="ui-tjsp", kind="tjsp", code="0000001-48.2024.8.26.0000", status="falhou",
                   verified=False, created_at="2026-10-28T12:00:00Z", finished_at="2026-10-28T12:01:00Z",
                   message="Consulta sem confirmação", frames=[], result={"resposta_widget_recebida": True, "consulta_enviada": True})
        self.page.evaluate("job => render(job)", job)
        self.assertEqual(self.page.locator("#run-status").inner_text(), "NÃO CONFIRMADO")
        self.assertIn("Tela de retorno registrada · não confirmado", self.page.locator(".tjsp-steps").inner_text())
        job.update(status="concluido", verified=True)
        self.page.evaluate("job => render(job)", job)
        self.assertEqual(self.page.locator("#run-status").inner_text(), "RETORNO RECEBIDO")
        job['result']['resultado'] = 'processo_aberto'
        self.page.evaluate("job => render(job)", job)
        self.assertEqual(self.page.locator("#run-status").inner_text(), "PROCESSO ABERTO")

    def test_sucesso_antigo_nao_e_reapresentado_ao_recarregar(self):
        with patch("web_demo.app.threading.Thread.start"):
            job = self.jobs.start("recaptcha", "")
        self.jobs.items[job["id"]].update(status="concluido", result={"validacao_servidor_confirmada": True})
        self.jobs.active = None
        self.page.reload()
        self.page.wait_for_function("document.querySelector('#connection').textContent === 'Disponível'")
        self.assertTrue(self.page.locator("#empty-state").is_visible())
        self.assertFalse(self.page.locator("#execution").is_visible())

    def test_demonstracao_nao_consulta_api_nem_altera_formulario(self):
        self.page.locator("#stj-parte").fill("Nome preservado ao apresentar")
        requests = []
        self.page.on("request", lambda request: requests.append((request.method, request.url)))
        self.page.locator("[data-demo-open]").first.click()
        self.assertIn("DADOS FICTÍCIOS", self.page.locator(".demo-badge").inner_text())
        self.page.locator("#demo-next").click()
        self.page.locator("#demo-next").click()
        self.assertIn("3", self.page.locator(".demo-result-count").inner_text())
        self.assertIn("inventados", self.page.locator("#demo-stage").inner_text())
        self.page.locator("#demo-next").click()
        self.assertEqual(self.page.locator("#demo-counter").inner_text(), "ETAPA 1 DE 3")
        self.page.keyboard.press("Escape")
        self.assertTrue(self.page.locator("#workspace").is_visible())
        self.assertEqual(self.page.locator("#stj-parte").input_value(), "Nome preservado ao apresentar")
        self.assertEqual(requests, [])
        self.assertIsNone(self.jobs.active)

    def test_demonstracao_responsiva_e_abertura_direta(self):
        self.page.goto(f"http://127.0.0.1:{self.server.server_port}/#demonstracao")
        self.page.locator("#demo-view").wait_for(state="visible")
        self.assertTrue(self.page.locator("#demo-view").is_visible())
        for width in (1366, 768, 390, 320):
            self.page.set_viewport_size({"width": width, "height": 900})
            for step in range(3):
                self.page.locator(f'[data-demo-step="{step}"]').click()
                self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
        self.page.locator('#demo-close').click()
        self.assertTrue(self.page.locator("#workspace").is_visible())

    def test_resultado_parcial_e_vazio_nao_prometem_ausencia_de_processos(self):
        job = dict(id="ui-exemplo", kind="stj", code="EMPRESA FICTICIA", status="falhou",
                   verified=False, created_at="2026-10-28T12:00:00Z", finished_at="2026-10-28T12:01:00Z",
                   message="Lista incompleta", frames=[], result={"resultado": "coleta_parcial",
                   "total_encontrados": 2, "processos": [dict(numero="EXEMPLO-01", partes="Nome ilustrativo")]})
        self.page.route("**/artifacts/tela.png", lambda route: route.fulfill(status=404))
        self.page.evaluate("job => render(job)", job)
        self.assertEqual(self.page.locator("#run-status").inner_text(), "RESULTADO PARCIAL")
        self.assertIn("1 registro coletado de 2", self.page.locator("#result-content").inner_text())
        job.update(status="concluido", verified=True, message="Nenhum registro retornado",
                   result={"total_encontrados": 0, "processos": []})
        self.page.evaluate("job => render(job)", job)
        self.assertIn("Nenhum registro encontrado", self.page.locator(".result-title").inner_text())
        self.assertIn("não significa ausência", self.page.locator("#result-content").inner_text())

    def test_enter_no_cnpj_envia_uma_unica_consulta(self):
        submissions = []
        def reject(route):
            submissions.append(route.request.post_data_json)
            route.fulfill(status=400, content_type="application/json", body='{"error":"Teste sem consulta externa"}')
        self.page.route("**/api/jobs", reject)
        self.page.locator("#trf3-cnpj").fill("00000000000000")
        self.page.locator("#trf3-cnpj").press("Enter")
        self.page.locator("#request-error").wait_for(state="visible")
        self.assertEqual(submissions, [dict(kind="trf3", code="00000000000000")])
        self.assertTrue(self.page.locator("#test-trf3").is_enabled())

    def test_troca_de_captura_oculta_imagem_anterior_ate_carregar_a_nova(self):
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4l8AAAAASUVORK5CYII=")
        self.page.route("**/artifacts/frame-001.png", lambda route: route.fulfill(content_type="image/png", body=png))
        pending = []
        self.page.route("**/artifacts/frame-002.png", lambda route: pending.append(route))
        with patch("web_demo.app.threading.Thread.start"):
            job = self.jobs.start("rastreamento", "AA123456785BR")
        item = self.jobs.items[job["id"]]
        item.update(status="falhou", result={}, frames=[
            dict(name="frame-001.png", title="Letras preenchidas automaticamente", created_at=item["created_at"]),
            dict(name="frame-002.png", title="Outra etapa", created_at=item["created_at"]),
        ])
        self.jobs.active = None
        self.page.evaluate("job => render(job)", self.jobs.public(item))
        self.page.locator("#capture-image").wait_for(state="visible")
        self.page.locator('[data-frame="frame-002.png"]').click()
        self.assertTrue(self.page.locator("#capture-image").is_hidden())
        self.assertTrue(self.page.locator("#enlarge-capture").is_hidden())
        self.assertIn("Outra etapa", self.page.locator("#capture-title").inner_text())
        pending[0].fulfill(content_type="image/png", body=png)
        self.page.locator("#capture-image").wait_for(state="visible")


if __name__ == "__main__":
    unittest.main()
