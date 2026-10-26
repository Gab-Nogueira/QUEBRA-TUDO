"use strict";
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const state = {job:null, timer:null, currentFrame:null, signature:""};
const EXAMPLE = "AA123456785BR";
const isLetters = job => job.kind === "rastreamento" || job.kind === "letras";
const artifact = (job, name) => `/api/jobs/${encodeURIComponent(job.id)}/artifacts/${encodeURIComponent(name)}`;
function dateTime(value) {return new Intl.DateTimeFormat("pt-BR", {timeZone:"America/Sao_Paulo",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}).format(new Date(value));}
function duration(job) {const seconds = Math.max(0,Math.floor((new Date(job.finished_at || Date.now()) - new Date(job.created_at))/1000)); return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds/60)}min ${seconds%60}s`;}
function connection(ok) {const node = $("#connection"); node.textContent = ok ? "Disponível" : "Sem conexão"; node.className = `connection ${ok ? "online" : "offline"}`;}
function busy(value) {document.querySelectorAll("[data-test]").forEach(button => button.disabled = value);}
function toast(message) {$("#toast").textContent = message; $("#toast").hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => $("#toast").hidden = true, 2500);}
async function json(url, options) {const response = await fetch(url,options); let data; try {data = await response.json();} catch {throw new Error("O serviço não respondeu como esperado.");} if (!response.ok) {const error = new Error(data.error || "Não foi possível iniciar o teste."); error.active = data.active; throw error;} return data;}
function showFrame(job, frame) {
  if (!frame) return;
  state.currentFrame = frame.name;
  const image = $("#capture-image");
  image.onload = () => {image.hidden = false; $("#capture-placeholder").hidden = true;};
  image.onerror = () => {image.hidden = true; $("#capture-placeholder").hidden = false;};
  image.src = artifact(job,frame.name);
  $("#capture-title").textContent = `${frame.title} · ${dateTime(frame.created_at)}`;
  $("#enlarge-capture").href = image.src;
  $("#enlarge-capture").hidden = false;
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
  const report = job.result || {};
  return isLetters(job) ? Boolean(report.consulta_confirmada && report.captcha_validado_pelo_servidor && report.rastreamento?.codigo === EXAMPLE) : Boolean(report.validacao_servidor_confirmada && !report.intervencao_humana);
}
function renderResult(job) {
  const report = job.result || {};
  if (job.status === "executando") return `<span class="result-eyebrow">EXECUTANDO AGORA</span><h2 class="result-title">Acompanhe esta tentativa.</h2><p class="live-phase">${esc(job.phase)}</p><div class="progress-track"><div class="progress-fill" style="width:${job.progress}%"></div></div>${job.recognized_text ? `<span class="answer-label">Texto reconhecido, ainda sem confirmação</span><div class="answer"><strong>${esc(job.recognized_text)}</strong></div>` : ""}<p class="running-details">As capturas são feitas no Chrome durante as etapas.<br><span id="elapsed">Tempo: ${duration(job)}</span></p>`;
  const ok = confirmed(job);
  if (!ok) {
    const message = report.resultado === "audio_bloqueado_pelo_google" ? "O Google limitou o acesso ao áudio nesta tentativa." : job.message || "O site não confirmou o resultado desta tentativa.";
    return `<span class="result-eyebrow">TENTATIVA ENCERRADA</span><h2 class="result-title failed">Não foi confirmado.</h2><p class="result-description">${esc(message)}</p><div class="unconfirmed">Nenhum sucesso foi atribuído a este teste. As capturas registradas continuam disponíveis ao lado.</div><p class="result-meta">Tempo total: ${duration(job)}</p>`;
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
  $("#empty-state").hidden = true;
  $("#execution").hidden = false;
  const letters = isLetters(job);
  document.querySelectorAll("[data-test]").forEach(button => button.classList.toggle("active",button.dataset.test === (letters ? "letras" : "recaptcha")));
  $("#run-kind").textContent = letters ? "Letras · Correios" : "reCAPTCHA · Google";
  $("#run-id").textContent = `ID ${job.id.slice(0,12)}`;
  $("#run-time").textContent = `Início: ${dateTime(job.created_at)}`;
  $("#source-host").textContent = letters ? "rastreamento.correios.com.br" : "google.com/recaptcha";
  $("#source-link").href = letters ? "https://rastreamento.correios.com.br/app/index.php" : "https://www.google.com/recaptcha/api2/demo";
  const ok = confirmed(job);
  $("#run-status").textContent = running ? "EM ANDAMENTO" : ok ? "CONFIRMADO PELO SITE" : "NÃO CONFIRMADO";
  $("#run-status").className = `status-badge ${running ? "" : ok ? "confirmed" : "failed"}`;
  const signature = JSON.stringify([job.id,job.status,job.progress,job.phase,job.recognized_text]);
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
  } catch (error) {connection(false); state.timer = setTimeout(() => watch(id),3000);}
}
document.querySelectorAll("[data-test]").forEach(button => button.addEventListener("click",async () => {
  $("#request-error").hidden = true;
  busy(true);
  try {
    const body = button.dataset.test === "letras" ? {kind:"rastreamento",code:EXAMPLE} : {kind:"recaptcha"};
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
