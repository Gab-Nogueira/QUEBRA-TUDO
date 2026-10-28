# Demonstração web

Interface local para acompanhar execuções de demonstração no navegador.

## Iniciar

Na pasta raiz do projeto, execute `scripts/INICIAR_WEB.cmd`. O endereço padrão é `http://localhost:5085`. O serviço roda em segundo plano.

## Dados da execução

Relatórios e estado ficam apenas na memória enquanto o serviço está ativo. A aplicação não grava capturas, áudio, histórico, resultados ou logs. Ao encerrar o serviço, esses dados transitórios desaparecem.

As consultas ainda enviam os campos necessários ao site de origem. O ambiente virtual, as dependências e o modelo de áudio são mantidos em `%LOCALAPPDATA%\CyolaConsultaAssistida` para o funcionamento do programa.
