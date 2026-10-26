# Consultas e CAPTCHA

## Demonstração web

Abra `INICIAR_WEB.cmd` e acesse `http://localhost:5085`. A página tem apenas **Letras** e **reCAPTCHA**, com execução nova a cada clique, capturas do Chrome e confirmação do site de origem. Consulte [web_demo/README.md](web_demo/README.md) para os detalhes da demonstração interna.

## Menu no CMD

Abra `TESTAR_RECAPTCHA.cmd`. O navegador padrão é o **Chrome**, conforme solicitado.

- Digite `1` ou `v1`: CAPTCHA de letras dos Correios, com reconhecimento local por OCR.
- Digite `2` ou `v2`: teste automático do Google reCAPTCHA v2 por áudio.
- Digite `0`: sair.

Na opção 1, informe um código de rastreamento para consultar ou pressione ENTER para somente ler a imagem. O programa mostra `CAPTCHA RECONHECIDO`, copia o texto para a área de transferência e preenche o campo no Chrome. Sem código de objeto, a janela permanece aberta até você pressionar ENTER no terminal, preservando a sessão da imagem lida. Leituras divergentes aparecem como alternativas; só reconhecer as letras não confirma que o servidor aceitou o CAPTCHA.

Com um código de objeto, a ferramenta envia a consulta e mostra situação, último local informado, destino em trânsito e previsão disponível. Confere se o objeto retornado é o mesmo consultado. Se a previsão estiver ausente, informa isso; se já tiver passado, sinaliza a data antiga. O último evento não representa localização em tempo real. CPF/CNPJ não é consultado automaticamente, pois a página direciona esse fluxo para login.

As evidências de letras e consultas ficam em `evidencias_correios\ID\`, com imagem, captura da página e relatório JSON. Há no máximo três tentativas quando a leitura é recusada. O teste com o código de exemplo `AA123456785BR` confirmou uma consulta aceita pelo servidor em `50a73e0a981a`; esse código não representa uma compra da empresa.

Também é possível executar diretamente pelo CMD ou PowerShell:

```powershell
.\TESTAR_RECAPTCHA.cmd --tipo 1
.\TESTAR_RECAPTCHA.cmd --tipo 1 --objeto SEU_CODIGO_DE_RASTREAMENTO
.\TESTAR_RECAPTCHA.cmd --tipo 2
```

Os nomes `v1` e `v2` funcionam como atalhos do menu. O CAPTCHA de letras dos Correios é Securimage, não o antigo serviço Google reCAPTCHA v1.

## Teste automático: somente reCAPTCHA

O modo padrão de `testar_recaptcha.py` abre a demonstração oficial do Google no Chrome, clica na caixa e, quando houver desafio, usa a opção de áudio. O modelo gratuito `base.en` do faster-whisper transcreve o áudio neste computador. O programa preenche e envia a resposta e confere a confirmação do formulário no servidor. Não pede seleção de imagens, intervenção nesta conversa ou chave de API.

**Neste computador o ambiente e o modelo já estão instalados.** Execute:

```powershell
.\TESTAR_RECAPTCHA.cmd --tipo 2
```

Também pode abrir `TESTAR_RECAPTCHA.cmd` com duplo clique e escolher 2 no menu. O carregamento inicial do modelo pode demorar alguns segundos. A resolução opera sem intervenção; o menu aguarda ENTER ao final para manter o resultado visível.

Em outro computador, execute primeiro `INSTALAR_AUTOMATICO.cmd`. A instalação baixa as dependências e o modelo aberto para `%LOCALAPPDATA%\CyolaConsultaAssistida`, sem serviço pago de reconhecimento. O modelo roda em CPU com duas threads. O PyAV está fixado em 15.1.0 para manter compatibilidade com faster-whisper 1.2.1.

As evidências ficam em `evidencias_recaptcha\ID\`, com captura de tela, relatório JSON e áudios usados. A aprovação exige `validacao_servidor_confirmada: true`. O relatório também distingue `resolucao_automatica_local` e `intervencao_humana`. A ferramenta não registra o token do reCAPTCHA.

O teste automático confirmou uma execução na demonstração oficial: `evidencias_recaptcha\0bed04557a62\resultado.json` e `tela.png`, com reconhecimento local em 2,06 segundos, resposta aceita na primeira tentativa e confirmação do servidor, sem intervenção humana. Isso comprova essa execução; ainda não estabelece uma taxa de acerto nem garante funcionamento em outros portais.

Há no máximo duas tentativas por desafio de áudio. Se o Google bloquear ou não oferecer áudio, se a transcrição for recusada ou se o servidor não confirmar, a execução registra a falha e encerra. Código de saída: 0 = confirmado; 1 = desafio não resolvido ou áudio bloqueado; 2 = erro técnico/inconclusivo.

Modos opcionais para diagnóstico:

```powershell
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" .\testar_recaptcha.py --apenas-clique
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" .\testar_recaptcha.py --interativo
```

O primeiro só mede o resultado do clique. O segundo mantém a bancada de seleção de imagens pelo terminal. O reconhecimento visual automático não foi implementado.

## Base de consulta para uma etapa posterior

Protótipo local em Python + Playwright. Preenche o formulário, aguarda o operador resolver o CAPTCHA no navegador, envia a consulta e exporta os campos configurados em JSON e CSV. Usa o Microsoft Edge instalado no Windows e não exige serviço pago de resolução.

**Estado atual:** base genérica com demonstração local. O site real ainda precisa ser informado e seus campos adaptados. Este protótipo não resolve CAPTCHA automaticamente, não implementa OCR e não é um resolvedor de reCAPTCHA.

## Como experimentar

Requisitos: Python 3.10 ou superior e Microsoft Edge instalado. No PowerShell, nesta pasta:

```powershell
.\INSTALAR.ps1
.\INICIAR.ps1 --demo
```

O navegador abre uma página local. Volte ao terminal e pressione ENTER para preencher o documento fictício. No navegador, digite `TESTE` no campo da etapa manual. Volte ao terminal e pressione ENTER para consultar e exportar. O navegador fecha ao concluir.

A instalação usa um ambiente Python separado em `%LOCALAPPDATA%\CyolaConsultaAssistida\venv`. Não inicia servidor nem altera o portal CYOLA. Os resultados ficam em `resultados\DATA-HORA-ID\`, em uma pasta nova por execução, sem substituir exportações anteriores.

## Adaptar ao site real

1. Copie `config.exemplo.json` para `config.local.json`.
2. Informe a URL e os seletores reais dos campos, do botão, da área que só fica visível após o sucesso e de cada dado retornado.
3. Se o site exibir mensagem de erro, informe o seletor em `erro_consulta`; caso contrário, remova essa propriedade.
4. Execute:

```powershell
.\INICIAR.ps1 --config .\config.local.json --campo documento=123456
```

É possível fornecer vários campos: `--campo documento=123456 --campo uf=SP`, desde que todos existam em `campos`. Nesta versão, o preenchimento usa campos de texto; listas, iframes e fluxos com várias telas exigem adaptação ao portal.

O navegador fica visível. Conclua eventual login antes de autorizar o preenchimento pelo terminal. Resolva o CAPTCHA no próprio site e pressione ENTER no terminal imediatamente depois; a ferramenta clica em Consultar. Se houver erro ou expiração, a consulta falha sem exportar um resultado como confirmado. Não há tentativas automáticas em série.

`campos_resultado` extrai o texto dos elementos. Configure seletores específicos e únicos. Se o site retornar documento/CNPJ, inclua esse campo para permitir a conferência da identidade consultada. A base genérica ainda não faz essa conferência automaticamente. CAPTCHA de texto e reCAPTCHA usam a mesma pausa manual; não há leitura, alteração ou reaproveitamento de tokens.

Para usar o Chrome, mude `navegador` para `chrome`. Para usar o Chromium do Playwright, escolha `chromium` e instale o binário com:

```powershell
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" -m playwright install chromium
```

## Próximos passos para automação completa

- Examinar o site real e procurar API oficial, exportação ou dados públicos que atendam à consulta.
- Para CAPTCHA de texto, avaliar OCR local em amostras variadas, medindo acertos antes de integrar. Não há taxa de acerto medida neste projeto.
- O reCAPTCHA v2 pode apresentar novos desafios após o clique na caixa. OCR de letras não resolve esse fluxo. A versão atual mantém a intervenção do operador.

## Verificação local

```powershell
& "$env:LOCALAPPDATA\CyolaConsultaAssistida\venv\Scripts\python.exe" -m unittest discover -s tests -v
```

Os testes usam somente a página fictícia local, sem acessar o site da empresa ou enviar consultas externas.

Referências: [Playwright para Python](https://playwright.dev/python/docs/library), [ddddocr](https://github.com/sml2h3/ddddocr), [faster-whisper](https://github.com/SYSTRAN/faster-whisper) e [rastreamento dos Correios](https://rastreamento.correios.com.br/app/).
