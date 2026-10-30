# Quebra Tudo — roteiro para os sócios

Abra `APRESENTAR.cmd` com dois cliques. O atalho inicia esta cópia na porta 5092 e abre a demonstração. Se o ambiente ainda não estiver instalado, execute antes `INSTALAR_AUTOMATICO.cmd`.

Na tela, use **Próxima etapa** ou os três passos do menu. **Voltar às consultas** abre a ferramenta real. A tecla **Esc** também sai da demonstração. Para ampliar a apresentação no navegador, use **F11**.

## Uma conversa de três minutos

**Abertura — o problema:** “Consultar informações em portais exige navegar por telas, preencher critérios e conferir o retorno. O Quebra Tudo reúne esse caminho e organiza o que foi encontrado.”

**1. A pergunta:** “Aqui a equipe escolhe onde consultar e quem procurar. Hoje temos TRF3 de primeiro grau por CNPJ e STJ por nome. Este exemplo é fictício, para mostrar o funcionamento.”

**2. O acompanhamento:** “Na consulta real, o sistema executa as etapas no portal. Podemos acompanhar o andamento e conferir as capturas. Se a consulta for interrompida, isso aparece na tela.”

**3. O resultado:** “O retorno fica organizado para análise, com os dados disponíveis e a origem para conferência. Os três registros desta tela são apenas ilustrativos.”

**Fechamento — o valor:** “A proposta é reduzir etapas manuais, organizar o retorno e dar visibilidade sobre o que aconteceu. Podemos escolher um caso de uso da equipe e medir o tempo e a qualidade do resultado em um piloto.”

## Para mostrar uma consulta real

1. Clique em **Voltar às consultas**.
2. Escolha o TRF3, o STJ ou o TJSP e informe um critério adequado à apresentação.
3. Inicie a consulta e acompanhe o resultado. O portal externo pode demorar ou bloquear o acesso.
4. Mostre os registros e as capturas. A confirmação só aparece quando a API valida a tentativa.

## Respostas objetivas para dúvidas

- **Consulta todos os tribunais?** Não. Esta versão oferece TRF3 de primeiro grau por CNPJ e STJ por nome. No TJSP, informe o número CNJ para abrir um processo de primeiro ou segundo grau. Escolha a instância (primeiro grau vem selecionado). Números fictícios também podem ser enviados para testar o avanço do formulário. “Retorno recebido” mostra a tela seguinte, inclusive quando não há processo; “Processo aberto” exige número conferido na página de detalhes e captura. Uma tela de erro não comprova, sozinha, aceitação do antirrobô. Se houver verificação interativa, conclua na janela do tribunal. Turmas recursais não estão incluídas.
- **A lista é sempre completa?** Não. Páginas seguintes não são coletadas nesta versão; respostas parciais são sinalizadas. O STJ não inclui andamentos detalhados.
- **Um nome encontrado comprova que é a mesma empresa?** Não. Nomes semelhantes precisam de conferência e a pesquisa do STJ não confirma vínculo com CNPJ.
- **Quanto tempo ou dinheiro economiza?** Ainda não há uma medição validada. O piloto deve comparar o mesmo trabalho manual e com a ferramenta, registrando tempo, erros e cobertura.
- **Onde ficam os dados?** As consultas reais guardam capturas, relatórios e histórico no computador que executa o serviço. A demonstração guiada usa apenas exemplos na interface e não cria consultas nem relatórios.

Comece pela demonstração para explicar o valor. Use a consulta real em seguida, caso queira comprovar o fluxo naquele momento.
