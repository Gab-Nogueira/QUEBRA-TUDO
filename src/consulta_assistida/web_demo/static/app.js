"use strict";

const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const state = {job:null, timer:null};
const EXAMPLE = "AA123456785BR";
const isLetters = job => job.kind === "rastreamento" || job.kind === "letras";

function dateTime(value) {
  return new Intl.DateTimeFormat("pt-BR", {timeZone:"America/Sao_Paulo",day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"}).format(new Date(value));
}

function duration(job) {
  const seconds = Math.max(0, Math.floor((new Date(job.finished_at || Date.now()) - new Date(job.created_at)) / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}min ${seconds % 60}s`;
}

function connection(ok) {
  const node = $("#connection");
  node.textContent = ok ? "Disponível" : "Sem conexão";
  node.className = `connection ${ok ? "online" : "offline"}`;
}

function busy(value) {
  document.querySelectorAll("[data-test]").forEach(button => button.disabled = value);
}

async function json(url, options) {
  const response = await fetch(url, {...options, cache:"no-store"});
  let data;
  try { data = await response.json(); }
  catch { throw new Error("O serviço não respondeu como esperado."); }
  if (!response.ok) {
    const error = new Error(data.error || "Não foi possível iniciar o teste.");
    error.active = data.active;
    throw error;
  }
  return data;
}

function confirmed(job) {
  const report = job.result || {};
  return isLetters(job)
    ? Boolean(report.consulta_confirmada && report.captcha_validado_pelo_servidor && report.rastreamento?.codigo === job.code)
    : Boolean(report.validacao_servidor_confirmada && !report.intervencao_humana);
}

function renderResult(job) {
  const report = job.result || {};
  if (job.status === "executando") {
    return `<span class="result-eyebrow">EXECUTANDO AGORA</span><h2 class="result-title">Acompanhe esta tentativa.</h2><p class="live-phase">${esc(job.phase)}</p><div class="progress-track"><div class="progress-fill" style="width:${job.progress}%"></div></div>${job.recognized_text ? `<span class="answer-label">Texto reconhecido, aguardando confirmação</span><div class="answer"><strong>${esc(job.recognized_text)}</strong></div>` : ""}<p class="running-details">Os dados ficam apenas na memória durante esta execução.<br>Tempo: ${duration(job)}</p>`;
  }

  if (!confirmed(job)) {
    const message = report.erro || report.mensagem_correios || job.message || "O site não confirmou o resultado desta tentativa.";
    return `<span class="result-eyebrow">TENTATIVA ENCERRADA</span><h2 class="result-title failed">Não foi confirmado.</h2><p class="result-description">${esc(message)}</p><div class="unconfirmed">Nenhum resultado, captura ou histórico desta execução foi gravado.</div><p class="result-meta">Tempo total: ${duration(job)}</p>`;
  }

  if (isLetters(job)) {
    const attempt = [...(report.tentativas || [])].reverse().find(item => item.aceita_pelo_servidor);
    const rastreamento = report.rastreamento || {};
    return `<span class="result-eyebrow">CONFIRMAÇÃO DOS CORREIOS</span><h2 class="result-title">Consulta confirmada.</h2><span class="answer-label">Código consultado</span><div class="answer"><strong>${esc(rastreamento.codigo || job.code)}</strong></div><p>${esc(rastreamento.situacao || "")}</p><p>${esc(rastreamento.ultimo_local_informado || "")}</p><div class="check-row"><span>✓</span> Resposta confirmada pelos Correios.</div><p class="result-meta">O resultado fica disponível somente enquanto esta página e o serviço estiverem ativos. Nenhum arquivo foi gravado.</p>`;
  }

  const attempt = (report.tentativas_audio || []).find(item => item.aceita_pelo_widget);
  return `<span class="result-eyebrow">CONFIRMAÇÃO DO GOOGLE</span><h2 class="result-title">O Google confirmou.</h2><div class="source-message">${esc(report.confirmacao_texto || "")}</div>${attempt ? `<span class="answer-label">Transcrição reconhecida</span><div class="answer speech"><strong>${esc(attempt.transcricao)}</strong></div>` : ""}<div class="check-row"><span>✓</span> Confirmação obtida na demonstração oficial.</div><p class="result-meta">O resultado fica disponível somente enquanto esta página e o serviço estiverem ativos. Nenhum arquivo foi gravado.</p>`;
}

function render(job) {
  state.job = job;
  const running = job.status === "executando";
  const letters = isLetters(job);
  busy(running);
  $("#empty-state").hidden = true;
  $("#execution").hidden = false;
  document.querySelectorAll("[data-test]").forEach(button => button.classList.toggle("active", button.dataset.test === (letters ? "letras" : "recaptcha")));
  $("#run-kind").textContent = letters ? "Letras · Correios" : "reCAPTCHA · Google";
  $("#run-id").textContent = `ID temporário ${job.id.slice(0,12)}`;
  $("#run-time").textContent = `Início: ${dateTime(job.created_at)}`;
  $("#source-host").textContent = letters ? "rastreamento.correios.com.br" : "google.com/recaptcha";
  $("#source-link").href = letters ? "https://rastreamento.correios.com.br/app/index.php" : "https://www.google.com/recaptcha/api2/demo";
  $("#run-status").textContent = running ? "EM ANDAMENTO" : confirmed(job) ? "CONFIRMADO PELO SITE" : "NÃO CONFIRMADO";
  $("#run-status").className = `status-badge ${running ? "" : confirmed(job) ? "confirmed" : "failed"}`;
  $("#result-content").innerHTML = renderResult(job);
  $("#capture-placeholder").textContent = running
    ? "Capturas desativadas para não gravar dados da consulta."
    : "Nenhuma captura foi salva nesta execução.";
  $("#capture-title").textContent = "Capturas desativadas";
}

function showPending(kind, code) {
  const letters = kind === "rastreamento";
  render({
    id: "aguardando",
    kind,
    title: letters ? "Rastreamento dos Correios" : "Verificação reCAPTCHA",
    code,
    created_at: new Date().toISOString(),
    status: "executando",
    progress: 12,
    phase: "Processando no servidor; o resultado aparece ao final.",
    message: "Aguarde a conclusão desta tentativa.",
    result: null
  });
}

async function watch(id) {
  clearTimeout(state.timer);
  try {
    const job = await json(`/api/jobs/${encodeURIComponent(id)}`);
    connection(true);
    render(job);
    if (job.status === "executando") state.timer = setTimeout(() => watch(id), 1000);
  } catch {
    connection(false);
    state.timer = setTimeout(() => watch(id), 3000);
  }
}

document.querySelectorAll("[data-test]").forEach(button => button.addEventListener("click", async () => {
  $("#request-error").hidden = true;
  busy(true);
  try {
    const body = button.dataset.test === "letras" ? {kind:"rastreamento",code:EXAMPLE} : {kind:"recaptcha"};
    showPending(body.kind, body.code || "");
    const job = await json("/api/jobs", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    render(job);
    if (job.status === "executando") watch(job.id);
  } catch (error) {
    if (!error.active) {
      $("#execution").hidden = true;
      $("#empty-state").hidden = false;
    }
    $("#request-error").textContent = error.message;
    $("#request-error").hidden = false;
    busy(false);
    if (error.active) watch(error.active);
  }
}));

json("/api/health").then(data => {
  connection(true);
  if (data.active) watch(data.active);
}).catch(() => connection(false));
