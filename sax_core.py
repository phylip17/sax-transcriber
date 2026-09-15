"""
sax_core.py

Logica compartilhada: baixar audio do YouTube, extrair a melodia (pitch
tracking) e transpor as notas para a leitura do Sax Alto em Eb.

Usado tanto pelo script de linha de comando (sax_transcriber.py) quanto
pelo aplicativo web (app.py), para nao duplicar a logica em dois lugares.
"""

import os
import shutil
import subprocess
import tempfile

import numpy as np
import librosa


# Sax alto em Eb soa uma sexta maior ABAIXO da nota escrita.
# Ou seja: nota_escrita = nota_concertante + 9 semitons.
TRANSPOSE_SEMITONES = 9

MIN_NOTE_DURATION_S = 0.12   # ignora notas mais curtas que isso (ruido/artefato)
CONFIDENCE_THRESHOLD = 0.5   # confianca minima do pyin para considerar "voiced"


# Caminho onde o Render disponibiliza "Secret Files" em tempo de execucao.
# Se um arquivo cookies.txt existir ali, usamos ele para autenticar no YouTube
# e contornar o bloqueio "Sign in to confirm you're not a bot" que o YouTube
# aplica a pedidos vindos de servidores/datacenters.
CAMINHO_COOKIES = os.environ.get("YOUTUBE_COOKIES_FILE", "/etc/secrets/cookies.txt")


def baixar_audio(url_ou_busca: str, pasta_destino: str) -> str:
    """Baixa o audio (melhor qualidade) de uma URL do YouTube ou de uma busca,
    usando yt-dlp, e retorna o caminho do arquivo .wav gerado.
    Lanca RuntimeError em caso de falha (nao encerra o processo)."""
    saida_template = os.path.join(pasta_destino, "audio.%(ext)s")
    alvo = url_ou_busca if url_ou_busca.startswith("http") else f"ytsearch1:{url_ou_busca}"

    comando = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", saida_template,
    ]

    if os.path.exists(CAMINHO_COOKIES):
        # O yt-dlp tenta atualizar o arquivo de cookies apos o uso (renova a
        # sessao). /etc/secrets e somente leitura no Render, entao copiamos
        # o arquivo para a pasta temporaria (gravavel) antes de usar.
        cookies_gravavel = os.path.join(pasta_destino, "cookies.txt")
        shutil.copyfile(CAMINHO_COOKIES, cookies_gravavel)
        comando += ["--cookies", cookies_gravavel]

    comando.append(alvo)

    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        erro = resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else "erro desconhecido"
        raise RuntimeError(f"Falha ao baixar o audio ({erro})")

    caminho_wav = os.path.join(pasta_destino, "audio.wav")
    if not os.path.exists(caminho_wav):
        raise RuntimeError("O arquivo de audio nao foi gerado apos o download.")
    return caminho_wav


def extrair_melodia(caminho_audio: str):
    """Extrai a linha melodica principal via pYIN (librosa)."""
    y, sr = librosa.load(caminho_audio, sr=22050, mono=True)
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
    )
    hop_length = 512  # padrao do librosa.pyin
    tempo_por_frame = hop_length / sr
    return f0, voiced_flag, voiced_prob, tempo_por_frame


def transpor_para_sax_alto(nota_concertante: str) -> str:
    """Recebe uma nota concertante (ex: 'C4') e retorna a nota escrita para
    o Sax Alto em Eb, transposta 9 semitons acima."""
    midi = librosa.note_to_midi(nota_concertante)
    return librosa.midi_to_note(midi + TRANSPOSE_SEMITONES, unicode=False)


def agrupar_notas(f0, voiced_flag, voiced_prob, tempo_por_frame):
    """Converte a serie de frequencias quadro a quadro em uma sequencia de
    notas discretas, agrupando quadros consecutivos iguais e descartando
    notas muito curtas ou de baixa confianca."""
    eventos = []
    nota_atual = None
    inicio_atual = 0.0

    for i, (freq, voz, prob) in enumerate(zip(f0, voiced_flag, voiced_prob)):
        tempo = i * tempo_por_frame

        if voz and prob >= CONFIDENCE_THRESHOLD and not np.isnan(freq):
            nota = librosa.hz_to_note(freq, unicode=False)
        else:
            nota = None

        if nota != nota_atual:
            if nota_atual is not None:
                duracao = tempo - inicio_atual
                if duracao >= MIN_NOTE_DURATION_S:
                    eventos.append((nota_atual, duracao))
            nota_atual = nota
            inicio_atual = tempo

    if nota_atual is not None:
        duracao = (len(f0) * tempo_por_frame) - inicio_atual
        if duracao >= MIN_NOTE_DURATION_S:
            eventos.append((nota_atual, duracao))

    return eventos


def processar_stream(origem: str):
    """Gerador que emite eventos de progresso conforme processa, e termina
    emitindo o resultado final (ou um erro). Cada evento e um dict:
      {"tipo": "log", "mensagem": "..."}
      {"tipo": "erro", "mensagem": "..."}
      {"tipo": "resultado", "notas": [...]}
    """
    with tempfile.TemporaryDirectory() as pasta_tmp:
        yield {"tipo": "log", "mensagem": f"Baixando audio de: {origem}"}
        try:
            caminho_audio = baixar_audio(origem, pasta_tmp)
        except RuntimeError as exc:
            yield {"tipo": "erro", "mensagem": str(exc)}
            return

        yield {"tipo": "log", "mensagem": "Audio baixado. Analisando a melodia (pode levar 1-2 minutos)..."}
        f0, voiced_flag, voiced_prob, tempo_por_frame = extrair_melodia(caminho_audio)

        yield {"tipo": "log", "mensagem": "Agrupando as notas detectadas..."}
        eventos = agrupar_notas(f0, voiced_flag, voiced_prob, tempo_por_frame)

        if not eventos:
            yield {"tipo": "erro", "mensagem": "Nao foi possivel detectar uma melodia clara nesse audio."}
            return

        yield {"tipo": "log", "mensagem": f"{len(eventos)} notas detectadas. Transpondo para Sax Alto em Eb..."}
        notas_sax = [transpor_para_sax_alto(nota) for nota, _dur in eventos]

        yield {"tipo": "resultado", "notas": notas_sax}
