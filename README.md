# Quebra Tudo

Consultas públicas do **TRF3, STJ e TJSP**, com acompanhamento das etapas, capturas e resultados organizados em um painel local. Inclui uma demonstração guiada com dados fictícios para apresentar o funcionamento.

**Versão de 30/10/2026.** A branch `main` contém a versão local atual, incluindo a interface de apresentação e a consulta do TJSP por número. [Baixar ZIP atualizado](https://github.com/Gab-Nogueira/QUEBRA-TUDO/archive/refs/heads/main.zip) · [Guia para gravar o vídeo](GUIA_DO_VIDEO.md) · [Alterações](CHANGELOG.md)

## 1. Preparar o computador

- Windows de 64 bits, com acesso à internet.
- **Python 3.13 de 64 bits**, versão usada na validação. Baixe pelo [site oficial do Python](https://www.python.org/downloads/windows/). No instalador, marque **Add python.exe to PATH**. As dependências desta distribuição são destinadas a Python 3.10 a 3.13; use 3.13 para seguir este roteiro.
- [Google Chrome](https://www.google.com/chrome/) instalado. As consultas reais abrem o Chrome no computador que executa o sistema. Microsoft Edge é usado pela demonstração genérica opcional de terminal e por alguns testes.

Não é necessário instalar Git ou VS Code para usar o ZIP.

## 2. Baixar e instalar

1. Abra [Gab-Nogueira/QUEBRA-TUDO](https://github.com/Gab-Nogueira/QUEBRA-TUDO), confira a branch **main** e clique em **Code → Download ZIP**.
2. Clique com o botão direito no ZIP e escolha **Extrair Tudo**. Coloque a pasta em um local permanente, por exemplo `Documentos\QuebraTudo`. Não execute os atalhos de dentro do ZIP.
3. Abra a pasta extraída que contém este README e dê dois cliques em **INSTALAR_AUTOMATICO.cmd**.
4. Aguarde a mensagem **Instalacao concluida**. A primeira instalação baixa as bibliotecas e pode demorar conforme a conexão. Se houver erro, confira a mensagem na janela antes de continuar.

O instalador cria o ambiente em `%LOCALAPPDATA%\CyolaConsultaAssistida\venv` e instala também as dependências do painel. O modelo de áudio é baixado separadamente no primeiro teste de reCAPTCHA; ele não é necessário para a demonstração guiada ou as consultas dos tribunais.

## 3. Abrir e usar

Dê dois cliques em **INICIAR_WEB.cmd**. O navegador abre o painel em **http://localhost:5085**. Se a abertura automática não funcionar, copie esse endereço.

| Opção | O que informar | O que esperar |
| --- | --- | --- |
| TRF3 | CNPJ com dígitos verificadores válidos | Consulta pública de primeiro grau, com conferência do documento e do total coletado. |
| STJ | Nome da parte | Registros por nome; nomes semelhantes exigem conferência. Não confirma vínculo com CNPJ. |
| TJSP | Número CNJ e primeiro ou segundo grau | Envio da consulta e captura da resposta. “Processo aberto” exige número conferido na página de detalhes. |
| Demonstração guiada | Nenhum dado real | Exemplo fictício em três etapas, sem consultar portais externos. |

Escolha a consulta, preencha o campo e inicie. Acompanhe o andamento, o retorno e as capturas. Se o tribunal solicitar uma verificação interativa, conclua-a na janela do Chrome. As execuções são sequenciais dentro de cada instância.

**“Retorno recebido” não significa “Processo aberto”.** O TJSP pode responder que não encontrou informações. Uma busca vazia não comprova inexistência de processos. TRF3/STJ ainda não coletam páginas seguintes; listas incompletas ficam parciais. Andamentos detalhados do STJ e turmas recursais do TJSP não estão incluídos.

Os recursos de apoio incluem testes de letras/Correios e reCAPTCHA. O código dos Correios usado no painel é um exemplo, não uma encomenda do usuário; o terminal permite informar outro código. Portais externos podem mudar, ficar indisponíveis ou bloquear uma tentativa.

## 4. Apresentar ou gravar um vídeo

Depois de instalar, dê dois cliques em **APRESENTAR.cmd**. Ele abre **http://localhost:5092/#demonstracao**, com dados fictícios identificados. Avance pelas três etapas e use **Voltar às consultas** para retornar ao painel. **Esc** sai da demonstração; **F11** amplia a tela.

Use o [guia do vídeo](GUIA_DO_VIDEO.md) para mostrar download, instalação e uso. O [roteiro de apresentação](APRESENTACAO.md) ajuda a explicar o produto e seus limites.

## Solução de problemas

- **Python não encontrado:** instale Python 3.13 de 64 bits com a opção de PATH marcada. Feche a janela antiga e execute o instalador novamente.
- **Ambiente Python incompatível:** feche as instâncias do sistema quando não houver consultas em andamento. Preserve a pasta `%LOCALAPPDATA%\CyolaConsultaAssistida\venv` renomeando-a para `venv-anterior` e execute o instalador novamente com Python 3.13 instalado. Não renomeie a pasta inteira `CyolaConsultaAssistida`, que também contém histórico e modelos.
- **Falha ao instalar dependências:** confira a conexão e a mensagem de erro, depois execute `INSTALAR_AUTOMATICO.cmd` novamente. Não prossiga enquanto a instalação não concluir.
- **Chrome não encontrado:** instale o Google Chrome no computador que executa o sistema e tente novamente.
- **Porta ocupada por outra cópia ou versão:** abra um terminal na pasta extraída e execute `.\INICIAR_WEB.cmd --port 5086`. Acesse `http://localhost:5086`. O launcher não reutiliza uma instância de outra pasta ou revisão.
- **O painel continua aberto depois de fechar a janela:** o servidor permanece em segundo plano. Fechar a aba do navegador também não encerra o serviço.
- **O GitHub ainda mostra a versão antiga:** selecione a branch `main` e baixe um ZIP novo. Extraia em outra pasta; não misture arquivos de versões diferentes.

## Dados e execução local

Esta distribuição salva resultados, capturas e, quando aplicável, áudio nas pastas `evidencias_*`. O estado e os logs do servidor ficam em `%LOCALAPPDATA%\CyolaConsultaAssistida\web_demo_IDENTIFICADOR_PORTA`, separados por projeto e porta. Esses dados locais, configurações particulares e relatórios de consultas reais não fazem parte do pacote publicado.

O servidor permite acesso pela rede local e não tem autenticação própria. Esta é uma aplicação para execução local no Windows; não inclui implantação na Vercel. A implementação modular anterior permanece no histórico Git e na branch `arquivo-main-antes-2026-10-30`.

## Testes e opções de terminal

Depois da instalação, execute na pasta do projeto:

```powershell
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" -m unittest discover -s tests -v
```

Os testes usam dados fictícios, mocks e páginas locais; não iniciam consultas externas. Exigem Chrome e, para a base genérica, Edge. Aprovação nos testes não garante disponibilidade dos portais externos.

Para a base genérica com etapa manual, execute `INSTALAR.ps1` e depois `INICIAR.ps1 --demo`. Para adaptar outra consulta, use `config.exemplo.json` como referência e configure URL e seletores em `config.local.json`. Os atalhos `CONSULTAR_TRF3.cmd` e `CONSULTAR_STJ.cmd` oferecem consultas pelo terminal.
