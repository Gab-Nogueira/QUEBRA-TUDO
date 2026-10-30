# Interface local

Execute `INICIAR_WEB.cmd` na raiz: ele abre `http://localhost:5085` no navegador. A interface apresenta as consultas do TRF3 por CNPJ, STJ por nome e TJSP por número CNJ e instância, com explicações sobre cada fonte. Os testes de Letras e reCAPTCHA ficam na seção Recursos de apoio. As execuções são sequenciais dentro de cada instância.

Para apresentar o produto, execute `APRESENTAR.cmd`: abre `http://localhost:5092/#demonstracao`. A demonstração guiada tem três etapas, usa dados fictícios identificados e não cria tarefas na API nem consulta tribunais. O formulário e uma eventual consulta real em andamento são preservados ao entrar e sair da demonstração. Veja o roteiro em [APRESENTACAO.md](../APRESENTACAO.md).

O campo de consulta pode ser editado enquanto uma execução termina; a execução conserva o valor originalmente enviado. A tela só confirma o resultado quando a API retorna `verified: true`. Capturas e relatório pertencem à mesma tentativa.

O resultado diferencia retorno parcial, falha de confirmação e pesquisa sem registros. Uma busca vazia não é apresentada como prova de inexistência de processos. As consultas podem ser enviadas pelo botão ou pelo formulário com teclado.

O serviço permanece em segundo plano. Para uma porta diferente, use `INICIAR_WEB.cmd --port 5086`. O launcher não reutiliza outra pasta, revisão ou configuração. Veja o [README principal](../README.md) para instalação, armazenamento e limites.
