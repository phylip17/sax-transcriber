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

# Taxa de amostragem reduzida e duracao maxima do audio analisado. O plano
# gratuito do Render tem so 512MB de RAM e 0.1 CPU, e a analise de pitch
# (pYIN) e pesada nos dois quesitos - esses limites evitam estourar a
# memoria/tempo disponiveis, mesmo custando um pouco de precisao ritmica.
TAXA_AMOSTRAGEM = 16000
DURACAO_MAXIMA_S = 90    # 1min30 - o suficiente pra maior parte de uma melodia
# frame_length/hop_length customizados (maiores que o padrao do librosa)
# quebravam a decodificacao interna do pYIN (sequence.transition_local).
# Deixamos o pYIN usar seus proprios padroes (frame_length=2048,
# hop_length=512) e reduzimos o custo de CPU só via duracao e taxa de
# amostragem, que sao seguros de ajustar.


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
        # O cliente "tv" (o mesmo que a Smart TV do YouTube usa) nao exige o
        # "PO Token" de verificacao que o YouTube passou a cobrar de outros
        # clientes, desde que haja cookies de uma conta logada.
        "--extractor-args", "youtube:player_client=tv",
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
    # Carrega na taxa nativa do arquivo e corta a duracao manualmente, em vez
    # de deixar o librosa.load fazer duracao+reamostragem juntos (combinacao
    # que apresentou um bug de borda com o resamplers padrao 'soxr').
    y, sr_nativo = librosa.load(caminho_audio, sr=None, mono=True)
    limite_amostras = int(DURACAO_MAXIMA_S * sr_nativo)
    y = y[:limite_amostras]

    # Reamostra separadamente, com um metodo baseado em scipy (mais simples
    # e sem a mesma condicao de borda do soxr, o padrao do librosa).
    y = librosa.resample(y, orig_sr=sr_nativo, target_sr=TAXA_AMOSTRAGEM, res_type="scipy")
    sr = TAXA_AMOSTRAGEM

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


LIMIAR_PAUSA_FRASE_S = 0.4  # pausas a partir disso marcam quebra de frase/linha

# Alcance escrito "normal" do sax alto (do Bb3 grave ao F6 agudo, sem contar
# o registro altissimo, que exige tecnica avancada e dedilhados alternativos).
ALCANCE_MIN_MIDI = librosa.note_to_midi("Bb3")
ALCANCE_MAX_MIDI = librosa.note_to_midi("F6")

# Perfis de Krumhansl-Schmuckler para estimar a tonalidade a partir de quanto
# tempo cada classe de nota (Do, Do#, Re...) soa na melodia.
PERFIL_MAIOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
PERFIL_MENOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
NOMES_NOTAS_PT = ["Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si"]


def _segmentar(f0, voiced_flag, voiced_prob, tempo_por_frame):
    """Converte a serie de frequencias quadro a quadro numa lista de
    segmentos (nota OU silencio), cada um com seu valor, duracao e a
    confianca media do pYIN nesse trecho. Diferente de uma lista so de
    notas, aqui guardamos tambem as pausas - sao elas que usamos depois
    para detectar onde uma frase termina."""
    segmentos = []
    valor_atual = None
    inicio_atual = 0.0
    probs_atuais = []

    for i, (freq, voz, prob) in enumerate(zip(f0, voiced_flag, voiced_prob)):
        tempo = i * tempo_por_frame

        if voz and prob >= CONFIDENCE_THRESHOLD and not np.isnan(freq):
            valor = librosa.hz_to_note(freq, unicode=False)
        else:
            valor = None

        if valor != valor_atual:
            confianca_media = float(np.mean(probs_atuais)) if probs_atuais else 0.0
            segmentos.append({"valor": valor_atual, "duracao": tempo - inicio_atual, "confianca": confianca_media})
            valor_atual = valor
            inicio_atual = tempo
            probs_atuais = []

        probs_atuais.append(float(prob))

    confianca_media = float(np.mean(probs_atuais)) if probs_atuais else 0.0
    segmentos.append({
        "valor": valor_atual,
        "duracao": (len(f0) * tempo_por_frame) - inicio_atual,
        "confianca": confianca_media,
    })
    return segmentos


def agrupar_notas(segmentos):
    """Filtra os segmentos, mantendo so as notas (descarta silencios e
    notas curtas demais / ruido). Retorna lista de (nota, duracao, confianca)."""
    return [
        (s["valor"], s["duracao"], s["confianca"])
        for s in segmentos
        if s["valor"] is not None and s["duracao"] >= MIN_NOTE_DURATION_S
    ]


def verificar_alcance(nota: str) -> bool:
    """Retorna True se a nota (ja transposta, escrita para o sax) estiver
    fora do alcance normal do instrumento (Bb3 a F6) - pode ser erro de
    deteccao ou uma nota de registro altissimo, que exige tecnica avancada."""
    midi = librosa.note_to_midi(nota)
    return midi < ALCANCE_MIN_MIDI or midi > ALCANCE_MAX_MIDI


def estimar_tonalidade(eventos) -> str:
    """Estima a tonalidade da melodia usando o algoritmo de
    Krumhansl-Schmuckler: correlaciona quanto tempo cada uma das 12 classes
    de nota soa com os perfis tipicos de cada tonalidade maior/menor.
    Recebe eventos (nota, duracao, confianca) EM CONCERTO (antes de
    transpor), para refletir a tonalidade real da musica."""
    pesos = np.zeros(12)
    for nota, duracao, _confianca in eventos:
        classe = librosa.note_to_midi(nota) % 12
        pesos[classe] += duracao

    if not pesos.any():
        return None

    melhor = None
    for tonica in range(12):
        for modo, perfil in (("maior", PERFIL_MAIOR), ("menor", PERFIL_MENOR)):
            perfil_rotacionado = perfil[-tonica:] + perfil[:-tonica]
            correlacao = np.corrcoef(pesos, perfil_rotacionado)[0, 1]
            if melhor is None or correlacao > melhor[0]:
                melhor = (correlacao, tonica, modo)

    _correlacao, tonica, modo = melhor
    return f"{NOMES_NOTAS_PT[tonica]} {modo}"


def agrupar_em_frases(segmentos):
    """Agrupa as notas detectadas em 'frases', separando sempre que houver
    uma pausa de silencio >= LIMIAR_PAUSA_FRASE_S entre elas. E uma
    aproximacao das frases respiradas de uma melodia (uteis como linhas
    de uma letra). Retorna lista de listas de notas (nao transpostas)."""
    frases = []
    frase_atual = []

    for s in segmentos:
        if s["valor"] is None:
            if s["duracao"] >= LIMIAR_PAUSA_FRASE_S and frase_atual:
                frases.append(frase_atual)
                frase_atual = []
            continue
        if s["duracao"] >= MIN_NOTE_DURATION_S:
            frase_atual.append(s["valor"])

    if frase_atual:
        frases.append(frase_atual)

    return frases


def _analisar_e_transpor(caminho_audio: str):
    """Roda a analise de melodia + transposicao a partir de um arquivo de
    audio ja em disco. Gerador de eventos de progresso, igual processar_stream."""
    yield {"tipo": "log", "mensagem": "Audio pronto. Analisando a melodia (pode levar alguns minutos no servidor gratuito)..."}
    f0, voiced_flag, voiced_prob, tempo_por_frame = extrair_melodia(caminho_audio)

    yield {"tipo": "log", "mensagem": "Agrupando as notas detectadas..."}
    segmentos = _segmentar(f0, voiced_flag, voiced_prob, tempo_por_frame)
    eventos = agrupar_notas(segmentos)

    if not eventos:
        yield {"tipo": "erro", "mensagem": "Nao foi possivel detectar uma melodia clara nesse audio."}
        return

    yield {"tipo": "log", "mensagem": f"{len(eventos)} notas detectadas. Transpondo para Sax Alto em Eb..."}
    notas_sax = [transpor_para_sax_alto(nota) for nota, _dur, _conf in eventos]
    confiancas = [round(confianca, 2) for _nota, _dur, confianca in eventos]
    fora_do_alcance = [verificar_alcance(nota) for nota in notas_sax]

    frases_concertantes = agrupar_em_frases(segmentos)
    frases_sax = [[transpor_para_sax_alto(nota) for nota in frase] for frase in frases_concertantes]

    tonalidade = estimar_tonalidade(eventos)

    yield {
        "tipo": "resultado",
        "notas": notas_sax,
        "frases": frases_sax,
        "confiancas": confiancas,
        "fora_do_alcance": fora_do_alcance,
        "tonalidade": tonalidade,
    }


def processar_stream(origem: str):
    """Gerador que baixa do YouTube e emite eventos de progresso conforme
    processa, terminando com o resultado final (ou um erro). Cada evento e
    um dict:
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

        yield from _analisar_e_transpor(caminho_audio)


def processar_arquivo_stream(caminho_audio: str):
    """Mesmo pipeline de processar_stream, mas a partir de um arquivo de
    audio que o usuario ja enviou (sem passar pelo download do YouTube).
    Usado como alternativa quando o YouTube bloqueia o download no servidor."""
    yield from _analisar_e_transpor(caminho_audio)
