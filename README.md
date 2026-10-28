# Quebra Tudo — Consulta Assistida

Versão atualizada em 27/10/2026, com código organizado em `src/`, testes locais e resultados mantidos em memória. Repositório: https://github.com/Gab-Nogueira/QUEBRA-TUDO.

Para abrir no Windows, use **INICIAR_WEB.cmd** na pasta principal. Em uma instalação nova, execute **INSTALAR_AUTOMATICO.cmd** primeiro. Os atalhos também estão disponíveis em `scripts/`.

Projeto local em Python para consultas web acompanhadas pelo operador e demonstrações de navegador.

## O que contém

- Uma base configurável com Playwright para preencher formulários e exibir os dados retornados.
- Experimentos locais de rastreamento dos Correios e reconhecimento de CAPTCHA.
- Uma interface web local para acompanhar execuções temporárias.
- Testes com dados fictícios e uma página local.

## Começar no Windows

```powershell
.\scripts\INSTALAR.ps1
.\scripts\INICIAR.ps1 --demo
```

Para abrir a interface web, use `scripts\INICIAR_WEB.cmd`. Para instalar as dependências dos experimentos, use `scripts\INSTALAR_AUTOMATICO.cmd` e depois `scripts\TESTAR_RECAPTCHA.cmd`.

Consulte [docs/uso.md](docs/uso.md) para configuração e detalhes de execução.

## Implantar na Vercel

O repositório inclui configuração para importar o projeto na Vercel. O build prepara os arquivos estáticos e o Chromium headless. A interface aguarda cada execução terminar antes de mostrar o resultado; o processamento de Correios e CAPTCHA continua usando os mesmos módulos Python.

Na Vercel, as consultas rodam na infraestrutura remota. O modelo de áudio é baixado para `/tmp` e pode ser baixado novamente quando a instância for reiniciada. Resultados e histórico continuam apenas em memória; nenhum arquivo de consulta é criado. A duração da execução é limitada a 270 segundos.

Antes de compartilhar o endereço, restrinja o acesso ao deployment pela proteção de acesso da Vercel: os endpoints iniciam consultas e consomem recursos do projeto.

## Dados e privacidade

O programa não grava consultas, resultados, capturas, áudios, histórico ou logs. A interface mantém os dados temporariamente em memória e os descarta quando o serviço é encerrado. Os resultados aparecem na tela durante a execução.

Os campos informados ainda são enviados ao site consultado. O ambiente virtual, as dependências e os modelos de reconhecimento continuam armazenados em `%LOCALAPPDATA%\CyolaConsultaAssistida`; eles são componentes do programa, não registros das consultas. A configuração `config.local.json`, se criada por você, também continua sendo um arquivo local.

Pastas antigas de resultados e evidências são ignoradas pelo Git. O programa não as lê nem cria novas evidências. Arquivos que já existiam foram preservados.

## Estrutura

```text
src/consulta_assistida/   Código Python do projeto
  web_demo/               Interface e servidor de demonstração
  fixtures/               Página fictícia usada nos testes
tests/                    Testes automatizados
scripts/                  Atalhos de instalação e execução no Windows
docs/                     Guia de uso
```

## Desenvolvimento

Instale o projeto e as dependências base:

```powershell
python -m pip install -e .
```

Para os módulos experimentais e a interface web:

```powershell
python -m pip install -e ".[automatico,web]"
```

Para executar os testes:

```powershell
python -m unittest discover -s tests -v
```
