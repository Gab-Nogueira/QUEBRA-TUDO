# Letras e reCAPTCHA — demonstração interna

Uma página simples com dois botões: Letras e reCAPTCHA. Cada clique inicia um teste novo e mostra capturas do Chrome durante a execução, o texto enviado e a resposta externa. Usa os módulos Python existentes e modelos locais, com Chrome, Flask e Waitress.

## Abrir

Execute `..\INICIAR_WEB.cmd`. O launcher reutiliza o serviço se ele já estiver ativo e imprime os endereços disponíveis. O endereço padrão é `http://localhost:5085`; visitantes na rede usam o IP deste computador com a mesma porta. O serviço fica em segundo plano. O computador precisa permanecer ligado e conectado para atendê-los.

O serviço é separado do portal CYOLA e usa a porta 5085. O estado e os registros do servidor ficam em `%LOCALAPPDATA%\CyolaConsultaAssistida\web_demo`. Não há publicação em hospedagem externa.

## Apresentar

- **Letras:** captura o CAPTCHA dos Correios, reconhece as letras, preenche o formulário e envia uma consulta com `AA123456785BR`. Esse código é de exemplo e não representa uma compra da empresa. Só mostra confirmação quando os Correios retornam o objeto correto e o CAPTCHA foi aceito.
- **reCAPTCHA:** executa o teste automático por áudio na demonstração oficial do Google. Mostra o áudio utilizado, a transcrição e a confirmação do formulário.
- **Capturas:** mostram as etapas do navegador da mesma tentativa. Ao terminar, é possível selecionar as etapas anteriores e ampliar as imagens.
- **Registro:** o download JSON inclui o ID da execução, as datas, as capturas e o retorno do teste.

A página inicial não reapresenta sucessos anteriores. Somente retoma um teste se houver uma execução realmente em andamento. O histórico técnico e as evidências anteriores continuam preservados no servidor.

Os testes são sequenciais. Se outro visitante iniciar uma execução, a interface acompanha a execução ativa em vez de abrir processos concorrentes. Cada módulo mantém os limites de tentativas existentes. Falhas e restrições do site de origem são apresentadas sem marcar o retorno como confirmado.

O Chrome roda sem janela na configuração padrão da página. Os testes pelo CMD continuam com a janela visível. Para uma demonstração com o Chrome visível, o servidor pode ser iniciado com `app.py --chrome-visivel` quando não houver outra instância ativa.

## Verificação

As verificações de API e classificação ficam em `tests/test_web_demo.py`. Os testes de navegador e capturas desta versão ficam em `qa/simples-*`, incluindo as duas execuções reais, a disponibilidade das capturas durante o teste e a conferência do layout em celular. Não foi medida uma taxa de acerto. As evidências exibem o que ocorreu no processo local; não constituem uma certificação independente contra adulteração do computador ou do programa.
