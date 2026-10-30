"use strict";
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const state = {job:null, timer:null, currentFrame:null, signature:""};
const EXAMPLE = "AA123456785BR";
const isLetters = job => job.kind === "rastreamento" || job.kind === "letras";
const isCloudflare = job => job.kind === "cloudflare";
const isTrf3 = job => job.kind === "trf3";
const isStj = job => job.kind === "stj";
const isTjsp = job => job.kind === "tjsp";
const artifact = (job, name) => `/api/jobs/${encodeURIComponent(job.id)}/artifacts/${encodeURIComponent(name)}`;
function dateTime(value) {return new Intl.DateTimeFormat("pt-BR", {timeZone:"America/Sao_Paulo",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}).format(new Date(value));}
function duration(job) {const seconds = Math.max(0,Math.floor((new Date(job.finished_at || Date.now()) - new Date(job.created_at))/1000)); return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds/60)}min ${seconds%60}s`;}
function connection(ok) {const node = $("#connection"); node.textContent = ok ? "Disponível" : "Sem conexão"; node.className = `connection ${ok ? "online" : "offline"}`;}
function busy(value) {
  state.pending = value;
  document.querySelectorAll("[data-test]").forEach(button => button.disabled = value);
  $("#busy-notice").hidden = !value;
}
function toast(message) {$("#toast").textContent = message; $("#toast").hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $("#toast").hidden = true, 2500);}
async function json(url, options) {const response = await fetch(url,options); let data; try {data = await response.json();} catch {const error = new Error("O serviço não respondeu como esperado."); error.status = response.status; throw error;} if (!response.ok) {const error = new Error(data.error || "Não foi possível iniciar o teste."); error.active = data.active; error.status = response.status; throw error;} return data;}
function showFrame(job, frame) {
  if (!frame) return;
  state.currentFrame = frame.name;
  const image = $("#capture-image");
  image.hidden = true;
  $("#capture-placeholder").hidden = false;
  $("#capture-placeholder p").textContent = "Carregando a captura selecionada…";
  $("#capture-placeholder .spinner").hidden = false;
  image.onload = () => {image.hidden = false; $("#capture-placeholder").hidden = true; $("#enlarge-capture").hidden = false;};
  image.onerror = () => {image.hidden = true; $("#capture-placeholder").hidden = false; $("#enlarge-capture").hidden = true; $("#capture-placeholder p").textContent = "Captura indisponível nesta etapa."; $("#capture-placeholder .spinner").hidden = true;};
  image.src = artifact(job,frame.name);
  $("#capture-title").textContent = `${frame.title} · ${dateTime(frame.created_at)}`;
  $("#enlarge-capture").href = image.src;
  $("#enlarge-capture").hidden = true;
  document.querySelectorAll("[data-frame]").forEach(button => button.classList.toggle("selected",button.dataset.frame === frame.name));
}
function renderFrames(job) {
  const frames = job.frames || [];
  $("#frames").innerHTML = frames.map((frame,index) => `<button data-frame="${esc(frame.name)}" ${job.status === "executando" ? "disabled" : ""} title="${esc(frame.title)}">${index+1}. ${esc(frame.title)}</button>`).join("");
  if (frames.length) {
    const preferred = isLetters(job) ? [...frames].reverse().find(frame => frame.title === "Letras preenchidas automaticamente") || frames[frames.length-1] : frames[frames.length-1];
    const frame = job.status === "executando" ? frames[frames.length-1] : !state.currentFrame ? preferred : frames.find(frame => frame.name === state.currentFrame) || preferred;
    if ($("#capture-image").getAttribute("src") !== artifact(job,frame.name)) showFrame(job,frame);
    else document.querySelectorAll("[data-frame]").forEach(button => button.classList.toggle("selected",button.dataset.frame === frame.name));
  } else if (job.status !== "executando" && job.result) showFrame(job,{name:"tela.png",title:"Resposta final desta tentativa",created_at:job.finished_at || job.created_at});
}
function confirmed(job) {
  return job.status === "concluido" && job.verified === true;
}
function renderCourt(job) {
  const report = job.result || {};
  const records = Array.isArray(report.processos) ? report.processos.filter(p => p && typeof p === "object") : [];
  const ok = confirmed(job);
  const partial = !ok && report.resultado === "coleta_parcial";
  const stj = isStj(job);
  const total = Number.isInteger(report.total_encontrados) ? report.total_encontrados : null;
  const title = partial ? "Resultado parcial." : !ok ? "Consulta não confirmada." : total === 0 ? "Nenhum registro encontrado." : `${total} ${total === 1 ? "registro encontrado" : "registros encontrados"}.`;
  const context = stj ? `Nome pesquisado: ${esc(report.nome_consultado || job.code)}` : `CNPJ pesquisado: ${esc(report.cnpj_formatado || job.code)}`;
  const guidance = partial ? `${records.length} ${records.length === 1 ? "registro coletado" : "registros coletados"}${total !== null ? ` de ${total} informados pelo portal` : ""}. A lista está incompleta e precisa ser conferida.` : !ok ? "O site não confirmou esta tentativa. Confira as capturas antes de tentar novamente. Isso não significa que não existam processos." : total === 0 ? "O portal não retornou registros para este critério. Isso não significa ausência de processos em outros tribunais ou em outras formas de pesquisa." : "Confira os dados de cada registro abaixo e as capturas do portal ao lado.";
  const items = records.map(p => `<li><strong>${esc(p.numero || "Número não informado")}</strong>${stj ? `<span>Registro: ${esc(p.registro || "Não informado")}</span><p>Autuação: ${esc(p.autuacao || "Não informada")} · ${esc(p.tipo || "Tipo não informado")}</p><details><summary>Ver partes do processo</summary><p class="party-lines">${esc(p.partes || "Não informadas")}</p></details>` : `<span>${esc(p.classe || "Classe não informada")}</span><p>${esc(p.ultima_movimentacao || "Movimentação não informada")}</p><details><summary>Ver partes e assunto</summary><p>${esc(p.partes || "Partes não informadas")}</p><p>${esc(p.assunto || "Assunto não informado")}</p></details>`}</li>`).join("");
  return `<span class="result-eyebrow">${stj ? "STJ · BUSCA POR NOME" : "TRF3 · PRIMEIRO GRAU"}</span><h2 class="result-title ${ok ? "" : "failed"}">${title}</h2>${job.message && job.message !== guidance ? `<p class="result-description">${esc(job.message)}</p>` : ""}<div class="source-message">${context}</div><p class="result-description result-guidance">${esc(guidance)}</p>${items ? `<ol class="process-list" aria-label="Registros retornados">${items}</ol>` : ""}<p class="result-meta">${stj ? "Nomes iguais podem pertencer a pessoas ou empresas diferentes. Esta busca não confirma vínculo com um CNPJ e não inclui andamentos detalhados." : "Abrange os dados públicos desta consulta de primeiro grau. Processos sigilosos podem não aparecer."}<br>Tempo total: ${duration(job)}</p>`;
}
function renderResult(job) {
  const report = job.result || {};
  if (job.status === "executando") return `<span class="result-eyebrow">EXECUTANDO AGORA</span><h2 class="result-title">Acompanhe sua ${isStj(job) || isTrf3(job) || isTjsp(job) ? "consulta" : "verificação"}.</h2><p class="live-phase">${esc(job.phase)}</p><div class="progress-track" role="progressbar" aria-label="Progresso da consulta" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0,Math.min(100,Number(job.progress)||0))}"><div class="progress-fill" style="width:${Math.max(0,Math.min(100,Number(job.progress)||0))}%"></div></div>${job.recognized_text ? `<span class="answer-label">Texto reconhecido, ainda sem confirmação</span><div class="answer"><strong>${esc(job.recognized_text)}</strong></div>` : ""}<p class="running-details">As capturas mostram o que acontece no site de origem.<br><span id="elapsed">Tempo: ${duration(job)}</span></p>`;
  const ok = confirmed(job);
  if (isStj(job) || isTrf3(job)) return renderCourt(job);
  if (isTjsp(job)) {
    const opened = ok && report.resultado === "processo_aberto";
    const steps = [[true,"Número informado"],[report.resposta_widget_recebida === true,"Resposta da verificação recebida"],[report.consulta_enviada === true,"Consulta enviada ao TJSP"],[ok,"Tela de retorno registrada"],[opened,"Processo encontrado e número conferido"]];
    return `<span class="result-eyebrow">TJSP · CONSULTA POR NÚMERO</span><h2 class="result-title ${ok ? "" : "failed"}">${opened ? "O processo abriu no TJSP." : ok ? "O TJSP respondeu à consulta." : "O retorno não foi confirmado."}</h2><p class="result-description">${esc(job.message)}</p><div class="source-message">${esc(job.code)}${report.instancia ? `<br>${esc(report.instancia)}` : ""}</div>${report.digitos_verificadores_validos === false ? '<p class="result-meta">Número com dígitos verificadores inválidos, enviado sem alteração para testar o retorno do portal.</p>' : ""}<ol class="tjsp-steps">${steps.map(([done,label]) => `<li class="${done ? "done" : "pending"}"><span aria-hidden="true">${done ? "✓" : "—"}</span>${label}${done ? "" : " · não confirmado"}</li>`).join("")}</ol><p class="result-meta">A imagem ao lado registra esta tentativa no portal. Uma resposta de erro não comprova que um processo foi aberto ou que o antirrobô foi aceito pelo servidor.<br>Tempo total: ${duration(job)}</p>`;
  }
  if (isCloudflare(job)) {
    return `<span class="result-eyebrow">TESTE DO CLOUDFLARE NO TJSP</span><h2 class="result-title ${ok ? "" : "failed"}">${ok ? "Resposta da verificação recebida." : "A liberação não foi confirmada."}</h2><p class="result-description">${esc(job.message || "O teste foi encerrado sem confirmação.")}</p><div class="${ok ? "source-message" : "unconfirmed"}">Consulta processual: não realizada.<br>Aceitação pelo formulário do TJSP: não testada.</div><p class="result-meta">Para abrir um processo, use o campo “Número do processo” acima.<br>Tempo total: ${duration(job)}</p>`;
  }
  if (!ok) {
    const message = report.resultado === "audio_bloqueado_pelo_google" ? "O Google limitou o acesso ao áudio nesta tentativa." : job.message || "O site não confirmou o resultado desta tentativa.";
    return `<span class="result-eyebrow">TENTATIVA ENCERRADA</span><h2 class="result-title failed">Não foi confirmado.</h2><p class="result-description">${esc(message)}</p><div class="unconfirmed">Nenhum sucesso foi atribuído a este teste. As capturas registradas continuam disponíveis ao lado.</div><p class="result-meta">Tempo total: ${duration(job)}</p>`;
  }
  if (job.kind === "letras") {
    const attempt = (report.tentativas || []).at(-1);
    return `<span class="result-eyebrow">LEITURA DA IMAGEM</span><h2 class="result-title">Texto reconhecido.</h2><div class="answer"><strong>${esc(attempt?.texto || "")}</strong></div><p class="result-description">A leitura não foi enviada aos Correios. A aceitação do CAPTCHA pelo servidor ainda não foi verificada.</p>`;
  }
  if (isLetters(job)) {
    const attempt = [...(report.tentativas || [])].reverse().find(attempt => attempt.aceita_pelo_servidor);
    return `<span class="result-eyebrow">CONFIRMAÇÃO DOS CORREIOS</span><h2 class="result-title">Deu certo.<br>As letras foram aceitas.</h2><span class="answer-label">Texto enviado nesta tentativa</span><div class="answer"><strong>${esc(attempt?.texto || "")}</strong><button class="copy-button" data-copy="${esc(attempt?.texto || "")}">Copiar</button></div><div class="check-row"><span>✓</span> Resposta do site recebida e código de exemplo conferido.</div><div class="source-message">HTTP ${esc(report.http_status_validacao || "não registrado")} · ${esc(report.resposta_servidor?.codigo_retornado || report.rastreamento.codigo)}</div><p class="result-meta">Validação com ${esc(EXAMPLE)}, um código de exemplo.<br>Tempo total: ${duration(job)}<br>Os Correios renovam a imagem depois da consulta. As etapas mostram o desafio resolvido e o retorno separadamente.</p>`;
  }
  const attempt = (report.tentativas_audio || []).find(attempt => attempt.aceita_pelo_widget);
  return `<span class="result-eyebrow">CONFIRMAÇÃO DO GOOGLE</span><h2 class="result-title">Deu certo.<br>O Google confirmou.</h2><div class="source-message">${esc(report.confirmacao_texto)}</div>${attempt ? `<span class="answer-label">Transcrição enviada</span><div class="answer speech"><strong>${esc(attempt.transcricao)}</strong></div><audio class="audio-proof" controls preload="none" src="${artifact(job,"audio.mp3")}"></audio><p class="audio-caption">Áudio usado nesta mesma tentativa.</p>` : ""}<div class="check-row"><span>✓</span> Confirmação obtida no formulário oficial, sem intervenção para resolver.</div><p class="result-meta">HTTP ${esc(report.http_status_validacao || "não registrado")} · Tempo total: ${duration(job)}</p>`;
}
function render(job) {
  const changedJob = state.job?.id !== job.id;
  state.job = job;
  const running = job.status === "executando";
  if (changedJob) {state.currentFrame = null; state.signature = ""; $("#capture-image").hidden = true; $("#capture-image").removeAttribute("src"); $("#capture-placeholder").hidden = false; $("#enlarge-capture").hidden = true;}
  busy(running);
  $("#capture-placeholder p").textContent = running ? "Aguardando a primeira captura do site…" : "Nenhuma captura disponível nesta etapa.";
  $("#capture-placeholder .spinner").hidden = !running;
  $("#empty-state").hidden = true;
  $("#execution").hidden = false;
  const letters = isLetters(job);
  const cloudflare = isCloudflare(job);
  const trf3 = isTrf3(job);
  const stj = isStj(job);
  const tjsp = isTjsp(job);
  document.querySelectorAll("[data-test]").forEach(button => button.classList.toggle("active",button.dataset.test === (letters ? "letras" : cloudflare ? "cloudflare" : trf3 ? "trf3" : stj ? "stj" : "recaptcha")));
  $(".trf3-choice").classList.toggle("active",trf3);
  $(".stj-choice").classList.toggle("active",stj);
  $(".tjsp-choice").classList.toggle("active",tjsp);
  $("#run-kind").textContent = letters ? "Letras · Correios" : cloudflare ? "Cloudflare · TJSP" : trf3 ? "TRF3 · Consulta por CNPJ" : stj ? "STJ · Nome da parte" : "reCAPTCHA · Google";
  $("#run-id").textContent = `ID ${job.id.slice(0,12)}`;
  $("#run-time").textContent = `Início: ${dateTime(job.created_at)}`;
  $("#source-host").textContent = letters ? "rastreamento.correios.com.br" : cloudflare ? "eproc-consulta.tjsp.jus.br" : trf3 ? "pje1g.trf3.jus.br" : stj ? "processo.stj.jus.br" : "google.com/recaptcha";
  $("#source-link").href = letters ? "https://rastreamento.correios.com.br/app/index.php" : cloudflare ? "https://eproc-consulta.tjsp.jus.br/consulta_1g/externo_controlador.php?acao=tjsp@consulta_unificada_publica/consultar" : trf3 ? "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam" : stj ? "https://processo.stj.jus.br/processo/pesquisa/?aplicacao=processos.ea" : "https://www.google.com/recaptcha/api2/demo";
  const ok = confirmed(job);
  if (tjsp) {
    $("#run-kind").textContent = "TJSP · Número do processo";
    $("#source-host").textContent = "Consulta pública · TJSP";
    try {const host = new URL(job.result?.url_final).hostname; if (["esaj.tjsp.jus.br","eproc-consulta.tjsp.jus.br","eproc2g-consulta.tjsp.jus.br"].includes(host)) $("#source-host").textContent = host;} catch {}
    $("#source-link").href = "https://eproc-consulta.tjsp.jus.br/consulta_1g/externo_controlador.php?acao=tjsp@consulta_unificada_publica/consultar";
    document.querySelectorAll("[data-test]").forEach(button => button.classList.toggle("active",button.dataset.test === "tjsp"));
  }
  $("#run-status").textContent = running ? "EM ANDAMENTO" : ok ? (tjsp ? (job.result?.resultado === "processo_aberto" ? "PROCESSO ABERTO" : "RETORNO RECEBIDO") : cloudflare ? "RESPOSTA RECEBIDA" : job.kind === "letras" ? "LEITURA CONCLUÍDA" : "CONFIRMADO PELO SITE") : job.result?.resultado === "coleta_parcial" ? "RESULTADO PARCIAL" : "NÃO CONFIRMADO";
  $("#run-status").className = `status-badge ${running ? "" : ok ? "confirmed" : "failed"}`;
  const signature = JSON.stringify([job.id,job.status,job.progress,job.phase,job.recognized_text,job.verified,job.message,job.result]);
  if (state.signature !== signature) {$("#result-content").innerHTML = renderResult(job); state.signature = signature;}
  else if ($("#elapsed")) $("#elapsed").textContent = `Tempo: ${duration(job)}`;
  renderFrames(job);
  $("#run-actions").hidden = running || !job.result;
  $("#download-report").href = `/api/jobs/${encodeURIComponent(job.id)}`;
  $("#download-report").download = `execucao-${job.id.slice(0,12)}.json`;
}
async function watch(id) {
  clearTimeout(state.timer);
  try {
    const job = await json(`/api/jobs/${encodeURIComponent(id)}`);
    connection(true);
    if (state.job?.status === "executando" && job.status !== "executando") state.currentFrame = null;
    render(job);
    if (job.status === "executando") state.timer = setTimeout(() => watch(id),1000);
  } catch (error) {
    if (error.status === 404) {
      connection(true); busy(false); state.job = null;
      $("#execution").hidden = true; $("#empty-state").hidden = false;
      $("#request-error").textContent = "Esta execução não está mais disponível no serviço. Você pode iniciar outra tentativa.";
      $("#request-error").hidden = false;
      return;
    }
    connection(false); state.timer = setTimeout(() => watch(id),3000);
  }
}
async function startQuery(button) {
  if (state.pending) return;
  $("#request-error").hidden = true;
  const field = button.dataset.test === "tjsp" ? $("#tjsp-processo") : button.dataset.test === "trf3" ? $("#trf3-cnpj") : button.dataset.test === "stj" ? $("#stj-parte") : null;
  if (field && !field.reportValidity()) return;
  busy(true);
  try {
    const body = button.dataset.test === "letras" ? {kind:"rastreamento",code:EXAMPLE} : field ? {kind:button.dataset.test,code:field.value} : {kind:button.dataset.test};
    if (body.kind === "tjsp") body.instancia = $("#tjsp-instancia").value;
    const job = await json("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    render(job);
    $("#execution").focus({preventScroll:true});
    $("#execution").scrollIntoView({behavior:"smooth",block:"start"});
    watch(job.id);
  } catch (error) {$("#request-error").textContent = error.message; $("#request-error").hidden = false; $("#request-error").scrollIntoView({block:"center"}); busy(false); if (error.active) watch(error.active);}
}
document.querySelectorAll("[data-test]").forEach(button => {
  if (button.form) button.form.addEventListener("submit", event => {event.preventDefault(); startQuery(button);});
  else button.addEventListener("click", () => startQuery(button));
});
document.addEventListener("click",async event => {
  const frameButton = event.target.closest("[data-frame]");
  if (frameButton && state.job) showFrame(state.job,state.job.frames.find(frame => frame.name === frameButton.dataset.frame));
  const copy = event.target.closest("[data-copy]");
  if (copy) {try {if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(copy.dataset.copy); else {const area = document.createElement("textarea"); area.value = copy.dataset.copy; document.body.append(area); area.select(); const ok = document.execCommand("copy"); area.remove(); if (!ok) throw new Error();} toast("Texto copiado.");} catch {toast("Selecione o texto para copiar.");}}
});
// The presentation has its own state and never creates jobs or calls a court.
const demo = {step:0, opener:null};
const demoSteps = [
  {
    title:"Comece com uma pergunta simples.",
    description:"“Há registros em nome desta empresa no STJ?” Você escolhe a fonte e informa o nome. O sistema conduz a pesquisa a partir desse critério.",
    benefit:"Um ponto de partida claro para a equipe, sem precisar conhecer os detalhes do portal.",
    content:`<div class="demo-stage-header"><strong>Uma busca no STJ</strong><span>EXEMPLO FICTÍCIO</span></div><div class="demo-field"><span>Nome da empresa</span><strong>Empresa Exemplo Horizonte Ltda.</strong></div><div class="demo-field"><span>Onde procurar</span><strong>Superior Tribunal de Justiça · por nome</strong></div><p class="demo-stage-note">Este nome é ilustrativo. A demonstração não envia nenhuma pesquisa.</p>`
  },
  {
    title:"Acompanhe, sem ficar no escuro.",
    description:"Em uma consulta real, as etapas e as capturas mostram o que acontece no site. Se houver uma interrupção, o resultado é sinalizado para conferência.",
    benefit:"Visibilidade para entender se a busca terminou e o que precisa de atenção.",
    content:`<div class="demo-stage-header"><strong>O caminho da consulta</strong><span>ETAPAS ILUSTRATIVAS</span></div><ol class="demo-progress-list"><li><span>01</span><div><strong>Abrir o portal</strong><small>Acessar a fonte pública escolhida.</small></div></li><li><span>02</span><div><strong>Pesquisar o nome informado</strong><small>Aplicar o critério da consulta.</small></div></li><li><span>03</span><div><strong>Conferir a resposta</strong><small>Reunir os registros e as capturas disponíveis.</small></div></li></ol><p class="demo-stage-note">Representação do fluxo. Nenhuma execução está acontecendo nesta demonstração.</p>`
  },
  {
    title:"Uma resposta que dá para conferir.",
    description:"Os registros aparecem organizados, com os dados disponíveis e as partes envolvidas. As capturas ajudam a conferir a origem da informação.",
    benefit:"A equipe recebe informação organizada para analisar, com clareza sobre o que foi encontrado e os limites da busca.",
    content:`<div class="demo-stage-header"><strong>Empresa Exemplo Horizonte Ltda.</strong><span>DADOS FICTÍCIOS</span></div><div class="demo-result-count"><strong>3</strong><span>registros neste exemplo</span></div><div class="demo-record"><div><strong>Registro ilustrativo 01</strong><small>Recurso · dados cadastrais</small></div><span>Exemplo</span></div><div class="demo-record"><div><strong>Registro ilustrativo 02</strong><small>Petição · dados cadastrais</small></div><span>Exemplo</span></div><div class="demo-record"><div><strong>Registro ilustrativo 03</strong><small>Agravo · dados cadastrais</small></div><span>Exemplo</span></div><p class="demo-stage-note">Os três registros são inventados. Na consulta real, nomes semelhantes exigem conferência e resultados incompletos são sinalizados.</p>`
  }
];
function renderDemo(step) {
  demo.step = Math.max(0,Math.min(2,step));
  const item = demoSteps[demo.step];
  $("#demo-counter").textContent = `ETAPA ${demo.step+1} DE 3`;
  $("#demo-step-title").textContent = item.title;
  $("#demo-description").textContent = item.description;
  $("#demo-benefit").textContent = item.benefit;
  $("#demo-stage").innerHTML = item.content;
  $("#demo-prev").disabled = demo.step === 0;
  $("#demo-next").textContent = demo.step === 2 ? "Recomeçar demonstração ↺" : "Próxima etapa →";
  document.querySelectorAll("[data-demo-step]").forEach(button => {
    if (Number(button.dataset.demoStep) === demo.step) button.setAttribute("aria-current","step");
    else button.removeAttribute("aria-current");
  });
}
function closeDemo(restoreFocus=true) {
  $("#workspace").hidden = false;
  $("#demo-view").hidden = true;
  if (location.hash === "#demonstracao") history.replaceState(null,"",location.pathname + location.search);
  if (restoreFocus) (demo.opener || document.querySelector("[data-demo-open]")).focus();
}
function openDemo(opener) {
  demo.opener = opener || document.querySelector("[data-demo-open]");
  renderDemo(0);
  $("#workspace").hidden = true;
  $("#demo-view").hidden = false;
  history.replaceState(null,"","#demonstracao");
  $("#demo-title").focus({preventScroll:true});
  window.scrollTo({top:0,behavior:"instant"});
}
document.querySelectorAll("[data-demo-open]").forEach(button => button.addEventListener("click",() => openDemo(button)));
document.querySelectorAll("[data-demo-step]").forEach(button => button.addEventListener("click",() => renderDemo(Number(button.dataset.demoStep))));
$("#demo-prev").addEventListener("click",() => renderDemo(demo.step-1));
$("#demo-next").addEventListener("click",() => renderDemo((demo.step+1)%3));
$("#demo-close").addEventListener("click",() => closeDemo());
document.querySelectorAll("[data-nav]").forEach(link => link.addEventListener("click",() => closeDemo(false)));
document.addEventListener("keydown",event => {if(event.key === "Escape" && !$("#demo-view").hidden) closeDemo();});
if (location.hash === "#demonstracao") openDemo();
window.addEventListener("hashchange",() => {
  if (location.hash === "#demonstracao") openDemo();
  else if (!$("#demo-view").hidden) closeDemo(false);
});
json("/api/health").then(async data => {
  connection(true);
  const selected = new URLSearchParams(location.search).get("consulta");
  const id = data.active || (/^[a-f0-9]{32}$/.test(selected || "") ? selected : null);
  if (id) {
    try {
      const job = await json(`/api/jobs/${id}`);
      if (job.status === "executando" || selected === id) {
        render(job);
        if (job.status === "executando") watch(job.id);
        if (selected === id && location.hash !== "#demonstracao") $("#execution").scrollIntoView({block:"start"});
      }
    } catch {$("#request-error").textContent = "Esta consulta não está disponível. Você pode iniciar uma nova tentativa."; $("#request-error").hidden = false;}
  }
}).catch(() => connection(false));
