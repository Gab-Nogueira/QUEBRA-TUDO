# Publicação de 30/10/2026

- Atualiza a branch principal e o Download ZIP com a versão local atual.
- Inclui a apresentação guiada e a consulta do TJSP por número, com primeiro/segundo grau e captura estável do retorno.
- Instala as dependências do painel junto com as demais bibliotecas; o modelo de áudio é baixado no primeiro teste que precisa dele.
- Localiza Python pelo launcher `py -3.13` ou pelo PATH e verifica versão e arquitetura.
- Abre o navegador ao executar `INICIAR_WEB.cmd`.
- Atualiza download, instalação, uso e solução de problemas e acrescenta `GUIA_DO_VIDEO.md`.
- Preserva a versão anterior da main na branch `arquivo-main-antes-2026-10-30` e no histórico.

# Revisão de 28/10/2026

## Interface para apresentação

- Apresenta a marca Quebra Tudo e os benefícios em linguagem simples.
- Destaca TRF3 e STJ e separa as consultas dos testes de acesso.
- Acrescenta demonstração guiada com dados fictícios, independente das consultas reais.
- Oferece o atalho `APRESENTAR.cmd` e um roteiro para a reunião.
- Melhora contraste, hierarquia, navegação por teclado e adaptação a telas pequenas.
- Diferencia resultados parciais, consultas não confirmadas e pesquisas sem registros.
- Mantém a confirmação baseada em `verified` e acrescenta testes da demonstração e dos formulários.

## Revisão funcional anterior

- Acrescenta os módulos e interfaces de TJSP, TRF3 e STJ à versão local.
- Identifica pasta, revisão e configuração antes de reutilizar o servidor.
- Separa o estado por projeto e porta, preservando arquivos inválidos para recuperação.
- Retorna HTTP 400 para tipos JSON inválidos e HTTP 503 quando a execução não pode iniciar, liberando a fila.
- Centraliza a confirmação do resultado no campo `verified` da API e considera o código de saída do processo.
- Evita confirmação com relatórios incompletos, identidade divergente ou booleanos em formato de texto.
- Recupera a interface quando uma execução deixa de existir e trata listas parciais.
- Oculta a captura anterior enquanto a nova carrega, mantendo imagem e legenda correspondentes.
- Preserva códigos de erro nos scripts e no atalho Windows.
- Inclui testes de regressão e de interface em Chrome, com dados fictícios.

Esta branch contém a implementação local que salva evidências. A implementação modular anterior e seu comportamento de resultados em memória continuam preservados no histórico Git.
