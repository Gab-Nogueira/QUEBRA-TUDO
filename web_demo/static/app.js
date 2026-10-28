"use strict";
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const state = {job:null, timer:null, currentFrame:null, signature:""};
const EXAMPLE = "AA123456785BR";
const isLetters = job => job.kind === "rastreamento" || job.kind === "letras";
const isCloudflare = job => job.kind === "cloudflare";
const isTrf3 = job => job.kind === "trf3";
const isStj = job => job.kind === "stj";
const artifact = (job, name) => `/api/jobs/${encodeURIComponent(job.id)}/artifacts/${encodeURIComponent(name)}`;
function dateTime(value) {return new Intl.DateTimeFormat("pt-BR", {timeZone:"America/Sao_Paulo",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}).format(new Date(value));}
function duration(job) {const seconds = Math.max(0,Math.floor((new Date(job.finished_at || Date.now()) - new Date(job.created_at))/1000)); return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds/60)}min ${seconds%60}s`;}
function connection(ok) {const node = $("#connection"); node.textContent = ok ? "Disponível" : "Sem conexão"; node.className = `connection ${ok ? "online" : "offline"}`;}
function busy(value) {document.querySelectorAll("[data-test]").forEach(button => button.disabled = value);}
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
function renderResult(job) {
  const report = job.result || {};
  if (job.status === "executando") return `<span class="result-eyebrow">EXECUTANDO AGORA</span><h2 class="result-title">Acompanhe esta tentativa.</h2><p class="live-phase">${esc(job.phase)}</p><div class="progress-track"><div class="progress-fill" style="width:${job.progress}%"></div></div>${job.recognized_text ? `<span class="answer-label">Texto reconhecido, ainda sem confirmação</span><div class="answer"><strong>${esc(job.recognized_text)}</strong></div>` : ""}<p class="running-details">As capturas são feitas no Chrome durante as etapas.<br><span id="elapsed">Tempo: ${duration(job)}</span></p>`;
  const ok = confirmed(job);
  if (isStj(job)) {
    const records = Array.isArray(report.processos) ? report.processos.filter(p => p && typeof p === "object") : [];
    const verification = report.recaptcha_observado ? "Verificação do Google observada; confira as etapas desta execução." : "Nenhum desafio interativo do Google foi observado nesta tentativa.";
    return `<span class="result-eyebrow">CONSULTA PÚBLICA DO STJ · POR NOME</span><h2 class="result-title ${ok ? "" : "failed"}">${ok ? `${report.total_encontrados} registros encontrados.` : "Consulta não confirmada."}</h2><p class="result-description">${esc(job.message)}</p><div class="source-message">Nome pesquisado: ${esc(report.nome_consultado || job.code)}</div>${records.length ? `<ol class="process-list">${records.map(p => `<li><strong>${esc(p.numero)}</strong><span>Registro: ${esc(p.registro)}</span><p>Autuação: ${esc(p.autuacao)} · ${esc(p.tipo)}</p><details><summary>Partes</summary><p class="party-lines">${esc(p.partes)}</p></details></li>`).join("")}</ol>` : ""}<p class="result-meta">${esc(verification)}<br>A listagem mostra dados cadastrais; os andamentos detalhados ainda não são coletados.<br>Tempo total: ${duration(job)}</p>`;
  }
  if (isTrf3(job)) {
    const records = Array.isArray(report.processos) ? report.processos.filter(p => p && typeof p === "object") : [];
    const captcha = report.desafio_interativo_observado ? "Verificação apresentada pelo site; confira as etapas." : "Nenhum desafio interativo foi observado nesta tentativa.";
    return `<span class="result-eyebrow">CONSULTA PÚBLICA DO TRF3 · 1º GRAU</span><h2 class="result-title ${ok ? "" : "failed"}">${ok ? `${report.total_encontrados} processos encontrados.` : "Consulta não confirmada."}</h2><p class="result-description">${esc(job.message)}</p><div class="source-message">CNPJ: ${esc(report.cnpj_formatado || job.code)}</div>${records.length ? `<ol class="process-list">${records.map(p => `<li><strong>${esc(p.numero)}</strong><span>${esc(p.classe)}</span><p>${esc(p.ultima_movimentacao)}</p><details><summary>Partes e assunto</summary><p>${esc(p.partes)}</p><p>${esc(p.assunto)}</p></details></li>`).join("")}</ol>` : ""}<p class="result-meta">${esc(captcha)}<br>Última movimentação exibida pelo portal; processos sigilosos podem não aparecer.<br>Tempo total: ${duration(job)}</p>`;
  }
  if (isCloudflare(job)) {
    return `<span class="result-eyebrow">TESTE DO CLOUDFLARE NO TJSP</span><h2 class="result-title ${ok ? "" : "failed"}">${ok ? "O desafio foi liberado." : "A liberação não foi confirmada."}</h2><p class="result-description">${esc(job.message || "O teste foi encerrado sem confirmação.")}</p><div class="${ok ? "source-message" : "unconfirmed"}">Consulta processual: não realizada.<br>Aceitação pelo formulário do TJSP: não testada.</div><p class="result-meta">Sem número de processo e sem serviço pago de resolução.<br>Tempo total: ${duration(job)}</p>`;
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
  $("#capture-placeholder p").textContent = running ? "Aguardando a primeira captura do Chrome…" : "Nenhuma captura disponível nesta etapa.";
  $("#capture-placeholder .spinner").hidden = !running;
  $("#empty-state").hidden = true;
  $("#execution").hidden = false;
  const letters = isLetters(job);
  const cloudflare = isCloudflare(job);
  const trf3 = isTrf3(job);
  const stj = isStj(job);
  document.querySelectorAll("[data-test]").forEach(button => button.classList.toggle("active",button.dataset.test === (letters ? "letras" : cloudflare ? "cloudflare" : trf3 ? "trf3" : stj ? "stj" : "recaptcha")));
  $(".trf3-choice").classList.toggle("active",trf3);
  $(".stj-choice").classList.toggle("active",stj);
  $("#run-kind").textContent = letters ? "Letras · Correios" : cloudflare ? "Cloudflare · TJSP" : trf3 ? "TRF3 · Consulta por CNPJ" : stj ? "STJ · Nome da parte" : "reCAPTCHA · Google";
  $("#run-id").textContent = `ID ${job.id.slice(0,12)}`;
  $("#run-time").textContent = `Início: ${dateTime(job.created_at)}`;
  $("#source-host").textContent = letters ? "rastreamento.correios.com.br" : cloudflare ? "eproc-consulta.tjsp.jus.br" : trf3 ? "pje1g.trf3.jus.br" : stj ? "processo.stj.jus.br" : "google.com/recaptcha";
  $("#source-link").href = letters ? "https://rastreamento.correios.com.br/app/index.php" : cloudflare ? "https://eproc-consulta.tjsp.jus.br/consulta_1g/externo_controlador.php?acao=tjsp@consulta_unificada_publica/consultar" : trf3 ? "https://pje1g.trf3.jus.br/pje/ConsultaPublica/listView.seam" : stj ? "https://processo.stj.jus.br/processo/pesquisa/?aplicacao=processos.ea" : "https://www.google.com/recaptcha/api2/demo";
  const ok = confirmed(job);
  $("#run-status").textContent = running ? "EM ANDAMENTO" : ok ? (cloudflare ? "DESAFIO LIBERADO" : job.kind === "letras" ? "LEITURA CONCLUÍDA" : "CONFIRMADO PELO SITE") : "NÃO CONFIRMADO";
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
document.querySelectorAll("[data-test]").forEach(button => button.addEventListener("click",async () => {
  $("#request-error").hidden = true;
  const field = button.dataset.test === "trf3" ? $("#trf3-cnpj") : button.dataset.test === "stj" ? $("#stj-parte") : null;
  if (field && !field.reportValidity()) return;
  busy(true);
  try {
    const body = button.dataset.test === "letras" ? {kind:"rastreamento",code:EXAMPLE} : field ? {kind:button.dataset.test,code:field.value} : {kind:button.dataset.test};
    const job = await json("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    render(job);
    watch(job.id);
  } catch (error) {$("#request-error").textContent = error.message; $("#request-error").hidden = false; busy(false); if (error.active) watch(error.active);}
}));
document.addEventListener("click",async event => {
  const frameButton = event.target.closest("[data-frame]");
  if (frameButton && state.job) showFrame(state.job,state.job.frames.find(frame => frame.name === frameButton.dataset.frame));
  const copy = event.target.closest("[data-copy]");
  if (copy) {try {if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(copy.dataset.copy); else {const area = document.createElement("textarea"); area.value = copy.dataset.copy; document.body.append(area); area.select(); const ok = document.execCommand("copy"); area.remove(); if (!ok) throw new Error();} toast("Texto copiado.");} catch {toast("Selecione o texto para copiar.");}}
});
json("/api/health").then(async data => {connection(true); if (data.active) {const job = await json(`/api/jobs/${data.active}`); if (job.status === "executando") {render(job); watch(job.id);}}}).catch(() => connection(false));
