# Revisão de 28/10/2026

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
