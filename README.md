# Quebra Tudo — versão local revisada

Versão de 28/10/2026 para execução local no Windows, com Correios, demonstração reCAPTCHA, teste do desafio TJSP, consulta pública do TRF3 por CNPJ e consulta pública do STJ por nome.

Esta versão mantém capturas, relatórios e histórico no computador que executa o serviço. É uma alternativa à versão modular com resultados em memória; não inclui implantação na Vercel.

## Executar

1. Instale Python 3.10 ou superior e Google Chrome. Os testes da base genérica também utilizam Microsoft Edge.
2. Execute `INSTALAR_AUTOMATICO.cmd` para instalar o ambiente e as dependências.
3. Execute `INICIAR_WEB.cmd` e abra `http://localhost:5085`.
4. Para outra porta, execute `INICIAR_WEB.cmd --port 5086`.

O ambiente fica em `%LOCALAPPDATA%\CyolaConsultaAssistida\venv`. O launcher confere a pasta, a revisão do código e a configuração do Chrome antes de reutilizar um serviço. Se outra versão ocupar a porta, use uma porta livre ou encerre a instância anterior quando estiver ociosa.

O servidor permite acesso pela rede local e não tem autenticação própria. TJSP, TRF3 e STJ abrem uma janela do Chrome no computador servidor. Correios e Google utilizam o modo sem janela na configuração padrão.

## Escopo dos resultados

- Correios: a tela usa um código de exemplo, que não representa uma encomenda do usuário. O terminal permite informar outro código.
- Google: a confirmação depende da resposta do formulário oficial da demonstração.
- TJSP: verifica somente a liberação do desafio; não envia pesquisa processual.
- TRF3: pesquisa pública de primeiro grau por CNPJ numérico, com conferência do documento e do total coletado.
- STJ: pesquisa por nome, sem confirmação de vínculo a CNPJ.

Paginação de TRF3/STJ e andamentos detalhados do STJ ainda não estão implementados. Listas incompletas permanecem parciais. Portais externos podem bloquear ou falhar; uma execução confirmada não estabelece taxa de acerto.

## Arquivos locais

As pastas `evidencias_*` armazenam resultados, capturas e, quando aplicável, áudio. O estado do servidor fica em `%LOCALAPPDATA%\CyolaConsultaAssistida\web_demo_IDENTIFICADOR_PORTA`, separado por projeto e porta. Esses arquivos, configurações particulares, backups e relatórios de consultas reais ficam fora do Git.

## Testes

```powershell
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" -m unittest discover -s tests -v
```

Os testes usam dados fictícios, mocks e páginas locais. Não iniciam consultas externas. A revisão adicionou verificações de falhas de inicialização, fila, classificação de resultados, identidade da instância, histórico inválido e interface no Chrome.

Para a base genérica com etapa manual, execute `INSTALAR.ps1` e depois `INICIAR.ps1 --demo`. Para adaptar outra consulta, use `config.exemplo.json` como referência e configure a URL e os seletores reais em `config.local.json`.

Veja [as alterações desta revisão](CHANGELOG.md).
