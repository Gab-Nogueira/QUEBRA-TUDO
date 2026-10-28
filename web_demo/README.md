# Interface local

Execute `INICIAR_WEB.cmd` na raiz e abra `http://localhost:5085`. As opções são Letras, reCAPTCHA, TJSP, TRF3 por CNPJ e STJ por nome. Os testes são sequenciais dentro de cada instância.

O campo de consulta pode ser editado enquanto uma execução termina; a execução conserva o valor originalmente enviado. A tela só confirma o resultado quando a API retorna `verified: true`. Capturas e relatório pertencem à mesma tentativa.

O serviço permanece em segundo plano. Para uma porta diferente, use `INICIAR_WEB.cmd --port 5086`. O launcher não reutiliza outra pasta, revisão ou configuração. Veja o [README principal](../README.md) para instalação, armazenamento e limites.
