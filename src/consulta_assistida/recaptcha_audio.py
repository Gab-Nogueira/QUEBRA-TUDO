"""Reconhecimento local de áudio para a bancada de demonstração do reCAPTCHA."""

from __future__ import annotations

import os
from pathlib import Path
import re
import time

from io import BytesIO


class ResolucaoAudioError(Exception):
    def __init__(self, motivo: str, detalhe: str):
        super().__init__(detalhe)
        self.motivo = motivo


class TranscritorLocal:
    def __init__(self, modelo: str = "base.en"):
        print(f"Carregando reconhecimento local {modelo}...", flush=True)
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ResolucaoAudioError("dependencia_ausente", "Execute scripts/INSTALAR_AUTOMATICO.cmd para instalar o reconhecimento local.") from exc
        self.modelo = modelo
        cache_configurada = os.environ.get("CYOLA_MODEL_CACHE_DIR")
        cache = (Path(cache_configurada) if cache_configurada else
                 Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CyolaConsultaAssistida" / "modelos")
        print(f"Carregando modelo local {modelo}. Na primeira vez, os arquivos serão baixados...", flush=True)
        self.reconhecedor = WhisperModel(modelo, device="cpu", compute_type="int8", cpu_threads=2,
                                        num_workers=1, download_root=str(cache))
        print("Reconhecimento local pronto.", flush=True)

    def transcrever(self, conteudo: bytes) -> str:
        segmentos, _ = self.reconhecedor.transcribe(BytesIO(conteudo), language="en", beam_size=5,
                                                   condition_on_previous_text=False, vad_filter=False)
        bruto = " ".join(segmento.text.strip() for segmento in segmentos)
        return " ".join(re.sub(r"[^a-zA-Z0-9' ]", " ", bruto).lower().split())


def verificar_bloqueio(frame) -> None:
    aviso = frame.locator(".rc-doscaptcha-header")
    if aviso.count() and aviso.is_visible():
        mensagem = frame.locator("body").inner_text().strip()
        raise ResolucaoAudioError("audio_bloqueado_pelo_google", mensagem)


def aguardar_audio(page, frame) -> str:
    prazo = time.monotonic() + 15
    while time.monotonic() < prazo:
        verificar_bloqueio(frame)
        audio = frame.locator("#audio-source")
        if audio.count():
            url = audio.get_attribute("src")
            if url:
                return url
        page.wait_for_timeout(200)
    raise ResolucaoAudioError("audio_indisponivel", "O desafio não disponibilizou um arquivo de áudio no prazo.")


def resolver_audio(page, transcritor: TranscritorLocal, relato: dict) -> bool:
    frame = page.frame_locator('iframe[src*="/recaptcha/api2/bframe"]')
    caixa = page.frame_locator('iframe[src*="/recaptcha/api2/anchor"]').locator("#recaptcha-anchor")
    verificar_bloqueio(frame)
    botao_audio = frame.locator("#recaptcha-audio-button")
    prazo_botao = time.monotonic() + 10
    while not botao_audio.count() or not botao_audio.is_visible():
        verificar_bloqueio(frame)
        if time.monotonic() >= prazo_botao:
            raise ResolucaoAudioError("audio_indisponivel", "Este desafio não exibiu o botão de áudio.")
        page.wait_for_timeout(200)
    print("Abrindo o desafio de áudio para resolução automática local...", flush=True)
    botao_audio.click()
    tentativas = relato.setdefault("tentativas_audio", [])
    for numero in range(1, 3):
        url = aguardar_audio(page, frame)
        resposta = page.context.request.get(url, timeout=20000)
        if not resposta.ok:
            raise ResolucaoAudioError("falha_download_audio", f"Download de áudio retornou HTTP {resposta.status}.")
        conteudo = resposta.body()
        if not conteudo or len(conteudo) > 5_000_000:
            raise ResolucaoAudioError("audio_invalido", "O arquivo de áudio está vazio ou fora do tamanho esperado.")
        inicio = time.monotonic()
        texto = transcritor.transcrever(conteudo)
        tentativa = {"numero": numero, "transcricao": texto, "duracao_transcricao_segundos": round(time.monotonic() - inicio, 2),
                     "aceita_pelo_widget": False}
        tentativas.append(tentativa)
        if not texto:
            raise ResolucaoAudioError("transcricao_vazia", "O modelo local não reconheceu fala no áudio recebido.")
        print(f"Tentativa {numero}: transcrição local concluída; enviando resposta...", flush=True)
        frame.locator("#audio-response").fill(texto)
        frame.locator("#recaptcha-verify-button").click()
        prazo = time.monotonic() + 20
        page.wait_for_timeout(750)
        while time.monotonic() < prazo:
            if caixa.get_attribute("aria-checked") == "true":
                tentativa["aceita_pelo_widget"] = True
                return True
            verificar_bloqueio(frame)
            erro = frame.locator(".rc-audiochallenge-error-message")
            if erro.count() and erro.is_visible() and erro.inner_text().strip():
                tentativa["erro_widget"] = erro.inner_text().strip()
                break
            page.wait_for_timeout(250)
        if numero < 2:
            frame.locator("#recaptcha-reload-button").click()
            page.wait_for_timeout(1000)
    raise ResolucaoAudioError("audio_nao_aceito", "O widget não aceitou a transcrição em duas tentativas. Execução encerrada.")
