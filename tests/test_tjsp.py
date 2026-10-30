"""Validação e navegação com páginas simuladas: nenhum processo real consultado."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from consultar_tjsp import normalizar_processo, detalhes_correspondem, consulta_confirmada, consultar_pagina, digitos_conferem, resposta_confirmada
from web_demo.app import create_app, classify_report

NUMERO = "0000001-48.2024.8.26.0000"  # Somente fixture; não implica existência.
URL2 = "https://eproc2g-consulta.tjsp.jus.br/eproc/externo_controlador.php"
DETAIL = f"<h1>{NUMERO}</h1><p>Classe: Teste</p><h2>Partes e representantes</h2><h2>Movimentações</h2>"


class TjspTests(unittest.TestCase):
    def test_numero_ficticio_e_enviado_sem_correcao(self):
        self.assertEqual(normalizar_processo("5364723-18.2024.8.26.0000"), "5364723-18.2024.8.26.0000")
        self.assertFalse(digitos_conferem("5364723-18.2024.8.26.0000"))
        with tempfile.TemporaryDirectory() as directory, patch("web_demo.app.threading.Thread.start") as start:
            client = create_app(state_dir=directory).test_client()
            response = client.post('/api/jobs', json=dict(kind='tjsp', code='5364723-18.2024.8.26.0000'))
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json['code'], '5364723-18.2024.8.26.0000')
            client.application.extensions['jobs'].active = None
            response = client.post('/api/jobs', json=dict(kind='tjsp', code=NUMERO.replace('-', '').replace('.', '')))
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json['code'], NUMERO)

    def test_formato_origem_e_texto_da_pagina(self):
        self.assertEqual(normalizar_processo(NUMERO), NUMERO)
        for bad in ('3090932/SP', 'abc'+NUMERO, NUMERO.replace('.8.26.', '.8.19.')):
            with self.assertRaises(ValueError):
                normalizar_processo(bad)
        self.assertTrue(detalhes_correspondem(URL2, DETAIL, NUMERO, False))
        for url, text, form in ((URL2, DETAIL, True), ('https://externo.invalid', DETAIL, False),
                                (URL2, DETAIL.replace(NUMERO, '9999999-99.2024.8.26.0000'), False),
                                (URL2, 'Consulta: '+NUMERO, False),
                                (URL2, DETAIL+' Processo não encontrado', False)):
            self.assertFalse(detalhes_correspondem(url, text, NUMERO, form))

    def test_token_e_navegacao_sem_captura_nao_confirmam(self):
        report = dict(resultado='processo_aberto', numero_consultado=NUMERO, numero_confirmado=NUMERO,
                      resposta_widget_recebida=True, consulta_enviada=True, pagina_processo_confirmada=True,
                      validacao_servidor_confirmada=True, captura_estavel=True, url_final=URL2, captura_resultado='frame-003.png')
        self.assertTrue(classify_report('tjsp', report, NUMERO)[0])
        for field in ('consulta_enviada', 'pagina_processo_confirmada', 'validacao_servidor_confirmada', 'captura_resultado'):
            invalid = {**report, field: None}
            self.assertFalse(consulta_confirmada(invalid))
        self.assertFalse(consulta_confirmada({**report, 'numero_consultado': '5364723-18.2024.8.26.0000'}))


class TjspNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(channel='chrome', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.p.stop()

    def run_fixture(self, *, details=DETAIL, token=True, instancia="TJSP"):
        context = self.browser.new_context()
        requests = []
        def respond(route):
            requests.append(route.request)
            second = 'eproc2g-' in route.request.url
            if route.request.method == 'POST':
                html = details
            else:
                html = f'''<form action="{URL2}" method="post"><input name="num_processo" id="txtNumProcesso">
                <select id="selInstancia" onchange="location.href='{URL2}'">
                <option value="SP" {'selected' if not second else ''}>Primeiro Grau</option>
                <option value="TJSP" {'selected' if second else ''}>Tribunal de Justiça</option></select>
                <input type="hidden" name="cf-turnstile-response" value="{'fixture-local' if token else ''}">
                <button type="submit">Consultar</button></form>'''
            route.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
        context.route('**/*', respond)  # Todas as requisições são locais e simuladas.
        page = context.new_page()
        try:
            with tempfile.TemporaryDirectory() as directory:
                report = dict(numero_consultado=NUMERO, instancia_codigo=instancia, _pasta=directory)
                stages = []
                result = consultar_pagina(page, report, espera=3, etapa=stages.append)
                if result == 0:
                    self.assertTrue((Path(directory)/report['captura_resultado']).is_file())
                return result, report, requests, stages
        finally:
            context.close()

    def test_seleciona_segundo_grau_envia_numero_e_captura_pagina(self):
        result, report, requests, stages = self.run_fixture()
        self.assertEqual(result, 0)
        self.assertTrue(consulta_confirmada(report))
        posts = [r for r in requests if r.method == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertIn('0000001-48.2024.8.26.0000', posts[0].post_data)
        self.assertEqual(report['instancia'], 'Tribunal de Justiça · 2º grau')

    def test_outro_processo_nao_confirma(self):
        result, report, _, _ = self.run_fixture(details=DETAIL.replace(NUMERO, '0000001-39.2024.8.26.0100'))
        self.assertEqual(result, 0)
        self.assertEqual(report['resultado'], 'retorno_sem_processo')
        self.assertFalse(consulta_confirmada(report))

    def test_primeiro_grau_e_preservado_mesmo_com_final_0000(self):
        result, report, requests, _ = self.run_fixture(instancia="SP")
        self.assertEqual(result, 0)
        self.assertEqual(report['instancia'], 'Primeiro grau')
        self.assertFalse(any('eproc2g-' in r.url and r.method == 'GET' for r in requests))

    def test_verificacao_pendente_nao_envia_formulario(self):
        result, report, requests, _ = self.run_fixture(token=False)
        self.assertEqual(result, 1)
        self.assertEqual(report['resultado'], 'verificacao_pendente')
        self.assertFalse(any(r.method == 'POST' for r in requests))

    def test_tela_de_erro_confirma_retorno_mas_nao_processo(self):
        result, report, _, _ = self.run_fixture(details='<h1>Número do processo inválido</h1>')
        self.assertEqual(result, 0)
        self.assertTrue(resposta_confirmada(report, NUMERO))
        self.assertFalse(consulta_confirmada(report))
        self.assertEqual(report['mensagem_portal'], 'Número inválido')

    def test_retorno_esaj_sem_informacoes_e_identificado(self):
        texto = 'Não existem informações disponíveis para os parâmetros informados'
        result, report, _, _ = self.run_fixture(details=f'<p>{texto}.</p>')
        self.assertEqual(result, 0)
        self.assertEqual(report['mensagem_portal'], texto)
        self.assertTrue(resposta_confirmada(report, NUMERO))
        self.assertFalse(consulta_confirmada(report))

    def test_transicao_em_branco_aguarda_pagina_estavel(self):
        html = '''<p>Preparando a próxima página do tribunal</p><script>
          setTimeout(() => document.body.innerHTML = '', 50);
          setTimeout(() => document.body.innerHTML = '<p>Não existem informações disponíveis para os parâmetros informados.</p>', 900);
        </script>'''
        result, report, _, _ = self.run_fixture(details=html)
        self.assertEqual(result, 0)
        self.assertTrue(report['captura_estavel'])
        self.assertEqual(report['mensagem_portal'], 'Não existem informações disponíveis para os parâmetros informados')


if __name__ == '__main__':
    unittest.main()
