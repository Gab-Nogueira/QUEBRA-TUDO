# Gravar o passo a passo do Quebra Tudo

## Antes de gravar

Use [Gab-Nogueira/QUEBRA-TUDO](https://github.com/Gab-Nogueira/QUEBRA-TUDO), na branch **main**. O README deve mostrar a versão **30/10/2026**. Para demonstrar a primeira instalação de verdade, use um computador ou usuário do Windows que ainda não tenha o ambiente instalado. No computador já preparado, o instalador reaproveita as bibliotecas existentes.

Tenha Python 3.13 de 64 bits e Chrome instalados, ou inclua a instalação deles no vídeo. Use a demonstração fictícia para gravar sem expor nomes, documentos, números de processos ou históricos reais. Feche abas e notificações que não devem aparecer.

## Sequência sugerida

1. **Apresentação:** “Vou mostrar como baixar, instalar e usar o Quebra Tudo no Windows. Ele reúne consultas de TRF3, STJ e TJSP em um painel local.”
2. **Download:** mostre a branch `main`, clique em **Code → Download ZIP** e aguarde.
3. **Extração:** use **Extrair Tudo**, escolha uma pasta permanente e abra a pasta que contém `README.md` e os atalhos. Explique que os arquivos precisam sair do ZIP antes de executar.
4. **Instalação:** abra `INSTALAR_AUTOMATICO.cmd`. Mostre a mensagem de conclusão. Se acelerar a gravação, informe que a primeira instalação baixa dependências e demora conforme a internet.
5. **Abertura:** abra `INICIAR_WEB.cmd`. Mostre o painel em `http://localhost:5085`. Não é necessário digitar comandos para o uso normal.
6. **Demonstração:** abra `APRESENTAR.cmd` ou a demonstração guiada pelo painel. Mostre as etapas de pergunta, acompanhamento e resultado. Diga que os dados são fictícios e não representam uma consulta real.
7. **Como consultar:** volte às consultas e mostre os campos: CNPJ no TRF3, nome no STJ, número CNJ e instância no TJSP. Se executar ao vivo, use um critério adequado e acompanhe o resultado que o portal realmente devolver.
8. **Como ler o retorno:** explique a diferença entre processo aberto, retorno recebido, resultado parcial e não confirmado. Mostre capturas quando disponíveis. Uma lista vazia não comprova ausência de processos.
9. **Encerramento:** mostre o README e seu endereço no GitHub. Explique que a ferramenta roda no computador, salva evidências localmente e depende da disponibilidade dos portais nas consultas reais.

## Se algo interromper a gravação

- Porta 5085 ocupada: use `.\INICIAR_WEB.cmd --port 5086` no terminal da pasta e acesse `http://localhost:5086`.
- Tribunal indisponível ou verificação manual: mostre o aviso como ele é; não apresente a demonstração fictícia como prova de consulta bem-sucedida.
- Primeiro teste de reCAPTCHA: o modelo de áudio precisa ser baixado. Isso é separado da demonstração guiada e das consultas dos tribunais.
- A apresentação abre na porta 5092. Se houver uma cópia antiga nessa porta, abra o painel em outra porta e use a demonstração por ele.

Consulte o [README](README.md) para pré-requisitos, armazenamento e solução de problemas; o [roteiro de apresentação](APRESENTACAO.md) traz uma explicação de três minutos.
