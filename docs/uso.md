# Guia de uso

Os comandos abaixo partem da pasta raiz do projeto no Windows. O instalador usa um ambiente Python separado em `%LOCALAPPDATA%\CyolaConsultaAssistida\venv`.

## Demonstração local

Requer Python 3.10 ou superior e Microsoft Edge instalado:

```powershell
.\scripts\INSTALAR.ps1
.\scripts\INICIAR.ps1 --demo
```

A demonstração usa dados fictícios da página `src/consulta_assistida/fixtures/consulta.html`. O resultado aparece no terminal e permanece apenas na memória durante a execução.

## Consulta configurável

Copie `config.exemplo.json` para `config.local.json` e ajuste a URL e os seletores do site:

```powershell
.\scripts\INICIAR.ps1 --config .\config.local.json --campo documento=123456
```

É possível enviar mais de um campo usando `--campo nome=valor`. A ferramenta abre um navegador temporário, pausa para o operador concluir login e verificações e exibe o retorno na tela. Ela não cria arquivos de resultado.

O conteúdo do formulário é enviado ao site consultado. A política sem gravação se refere aos dados que este projeto poderia reter no computador; ela não controla o site de origem, o sistema operacional ou ferramentas externas.

## Interface web

Execute `scripts\INICIAR_WEB.cmd` para abrir a interface em `http://localhost:5085`. Os resultados e o estado das execuções existem somente na memória do serviço e desaparecem quando ele é encerrado. A interface não guarda capturas, relatórios, histórico ou logs.

## Experimentos

`scripts\INSTALAR_AUTOMATICO.cmd` instala as dependências e prepara o modelo de áudio. Depois, `scripts\TESTAR_RECAPTCHA.cmd` abre o menu:

- `1`: leitura experimental de CAPTCHA de letras e consulta de rastreamento dos Correios.
- `2`: teste de áudio na página oficial de demonstração do Google.
- `0`: sair.

O modelo de áudio é armazenado em `%LOCALAPPDATA%\CyolaConsultaAssistida\modelos`. O áudio recebido durante uma execução é processado em memória e não é salvo pelo projeto. Os experimentos dependem do conteúdo apresentado pelo site e não garantem funcionamento em outros portais.

## Implantação na Vercel

Conecte o repositório GitHub à Vercel e mantenha a raiz do projeto como diretório do projeto. O `vercel.json` seleciona o runtime Flask, instala as dependências específicas e executa `scripts/vercel_build.py`, que publica os arquivos da interface e baixa o Chromium headless compatível com a versão instalada do Playwright.

Na Vercel, cada consulta é processada dentro da requisição HTTP; a página não exibe progresso ao vivo e mostra o resultado quando a execução termina. O tempo limite da consulta é 270 segundos. O modelo Whisper é baixado para `/tmp/CyolaConsultaAssistida/modelos`, que é temporário e pode ser limpo entre instâncias. Nenhum resultado, áudio ou histórico é gravado em arquivo.

A execução na nuvem pode receber respostas diferentes do site de origem. A lógica de consulta e de validação dos resultados foi mantida. Restrinja o acesso ao deployment antes de compartilhar o endereço, porque qualquer pessoa que consiga acessá-lo pode iniciar uma execução.

## Testes

Para executar a suíte a partir da raiz:

```powershell
python -m unittest discover -s tests -v
```

Os testes usam a página fictícia e validações locais. Eles não fazem consultas externas.
