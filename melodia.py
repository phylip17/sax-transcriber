"""
melodia.py

Etapas de "limpeza" do audio e das notas, feitas so com numpy/scipy (leve
para o plano gratuito do Render):

1. separar_voz     -> tira a parte repetitiva da musica (bateria, base,
                      acordes) e deixa o que muda: a voz/solo (REPET-SIM).
2. estimar_tempo   -> descobre o BPM e onde caem os tempos, para encaixar
                      as notas no compasso.
3. notas_de_f0     -> transforma a curva de afinacao do pYIN em notas
                      limpas: sem vibrato picotado, sem "erros de oitava",
                      sem notinhas-fantasma de deslize entre notas.
"""

import numpy as np
from scipy import signal


# ----------------------------------------------------------------------------
# Utilitarios
# ----------------------------------------------------------------------------

def _softmask(x, x_ref, potencia=2.0):
    """Mascara suave: x^p / (x^p + x_ref^p), estavel numericamente."""
    z = np.maximum(x, x_ref)
    z[z < 1e-10] = 1.0
    a = (x / z) ** potencia
    b = (x_ref / z) ** potencia
    return a / (a + b + 1e-10)


def _stft(y, n_fft, hop):
    # scipy, com janela centrada (igual ao librosa center=True): o quadro i
    # fica centrado em i*hop, alinhado com os quadros do pYIN.
    _f, _t, z = signal.stft(y, nperseg=n_fft, noverlap=n_fft - hop,
                            boundary="zeros", padded=True)
    return z.astype(np.complex64)


def _istft(z, n_fft, hop, tamanho):
    _t, y = signal.istft(z, nperseg=n_fft, noverlap=n_fft - hop,
                         boundary=True)
    y = y[:tamanho]
    if len(y) < tamanho:
        y = np.pad(y, (0, tamanho - len(y)))
    return y.astype(np.float32)


def _bandas_log(espectro, n_bandas=96):
    """Agrupa as frequencias em bandas logaritmicas (reduz o custo de
    comparar quadros entre si sem perder o 'formato' do som)."""
    n_freq = espectro.shape[0]
    bordas = np.unique(np.geomspace(1, n_freq, n_bandas + 1).astype(int) - 1)
    return np.add.reduceat(espectro, bordas, axis=0)


# ----------------------------------------------------------------------------
# 1. Separacao da voz/solo (REPET-SIM)
# ----------------------------------------------------------------------------

def separar_voz(y, sr, n_fft=2048, hop=512, vizinhos=30, distancia_min_s=2.0,
                margem=0.5):
    """Separa a linha principal (voz ou solo) do acompanhamento.

    Ideia (Rafii & Pardo, REPET-SIM): o acompanhamento se repete ao longo da
    musica; a voz nao. Para cada instante, buscamos os trechos mais
    parecidos da musica e tiramos a mediana deles: isso reconstroi o
    acompanhamento. O que sobra e a melodia.
    Retorna (y_voz, intensidade_voz_por_quadro)."""
    tamanho = len(y)
    z = _stft(y, n_fft, hop)
    mag = np.abs(z)
    n_quadros = mag.shape[1]

    largura = int(distancia_min_s * sr / hop)
    if n_quadros < 2 * largura + vizinhos + 5:
        # Audio curto demais para achar repeticoes: devolve como esta.
        return y.astype(np.float32), mag.sum(axis=0)

    # Similaridade (cosseno) entre todos os quadros, em bandas reduzidas
    feat = np.log1p(_bandas_log(mag)).astype(np.float32)
    feat /= np.linalg.norm(feat, axis=0, keepdims=True) + 1e-8
    sim = feat.T @ feat
    for k in range(-largura, largura + 1):
        idx = np.arange(max(0, -k), min(n_quadros, n_quadros - k))
        sim[idx, idx + k] = -np.inf
    k = min(vizinhos, n_quadros - 2 * largura - 1)
    vizinhos_idx = np.argpartition(-sim, k, axis=1)[:, :k]
    del sim

    # Mediana dos vizinhos = estimativa do acompanhamento (em blocos, para
    # nao estourar a memoria do servidor)
    acomp = np.empty_like(mag)
    bloco = 150
    for ini in range(0, n_quadros, bloco):
        fim = min(n_quadros, ini + bloco)
        acomp[:, ini:fim] = np.median(mag[:, vizinhos_idx[ini:fim]], axis=2)
    acomp = np.minimum(acomp, mag)

    mascara = _softmask(mag - acomp, margem * acomp)
    z_voz = mascara * z
    y_voz = _istft(z_voz, n_fft, hop, tamanho)
    return y_voz, (np.abs(z_voz) ** 2).sum(axis=0)


def energia_por_quadro(y, n_fft=2048, hop=512):
    return (np.abs(_stft(y, n_fft, hop)) ** 2).sum(axis=0)


def cromagrama_medio(y, sr, n_fft=4096, hop=2048):
    """Quanto cada uma das 12 notas (Do..Si) soa na musica inteira
    (melodia + acompanhamento). A harmonia da banda ajuda muito a acertar
    o tom - so a melodia as vezes engana."""
    mag = np.abs(_stft(y, n_fft, hop))
    freqs = np.arange(mag.shape[0]) * sr / n_fft
    validos = (freqs >= 65) & (freqs <= 2000)
    midi = 69 + 12 * np.log2(freqs[validos] / 440.0)
    classes = np.round(midi).astype(int) % 12
    energia = np.log1p(100 * mag[validos] / (mag[validos].max() + 1e-10)).sum(axis=1)
    croma = np.bincount(classes, weights=energia, minlength=12)
    return croma / (croma.sum() + 1e-10)


def estimar_tonalidade(notas, croma_musica=None):
    """Krumhansl-Schmuckler sobre as notas da melodia (midi concerto +
    duracao) somadas ao cromagrama da musica inteira, se houver.
    Retorna (tonica 0-11, 'maior'|'menor')."""
    maior = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    menor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    pesos = np.zeros(12)
    for nt in notas:
        pesos[nt["midi"] % 12] += nt["fim"] - nt["inicio"]
    if pesos.any():
        pesos /= pesos.sum()
    if croma_musica is not None:
        pesos = 0.4 * pesos + 0.6 * np.asarray(croma_musica)
    if not pesos.any():
        return 0, "maior"
    melhor = (-2.0, 0, "maior")
    for tonica in range(12):
        for modo, perfil in (("maior", maior), ("menor", menor)):
            rot = np.roll(perfil, tonica)
            r = np.corrcoef(pesos, rot)[0, 1]
            if r > melhor[0]:
                melhor = (r, tonica, modo)
    return melhor[1], melhor[2]


def ataques_por_quadro(energia_quadros):
    """Curva de 'ataques' (inicio de nota) a partir da energia por quadro
    da voz separada. Usada para separar notas repetidas na mesma altura."""
    log_e = np.log1p(1000 * energia_quadros / (energia_quadros.max() + 1e-10))
    fluxo = np.maximum(0, np.diff(log_e, prepend=log_e[0]))
    media = signal.convolve(fluxo, np.ones(15) / 15, mode="same")
    return np.maximum(0, fluxo - media)


# ----------------------------------------------------------------------------
# 2. Tempo (BPM) e fase dos tempos
# ----------------------------------------------------------------------------

def estimar_tempo(y, sr, bpm_min=60, bpm_max=180):
    """Estima o BPM (andamento constante) e o instante do primeiro tempo.
    Retorna (bpm_inteiro, fase_em_segundos)."""
    n_fft, hop = 1024, 128
    mag = np.abs(_stft(y, n_fft, hop))
    taxa = sr / hop
    log_mag = np.log1p(100 * _bandas_log(mag, 64))
    fluxo = np.maximum(0, np.diff(log_mag, axis=1)).sum(axis=0)
    fluxo = np.concatenate([[0], fluxo])
    janela = int(0.5 * taxa)
    fluxo = np.maximum(0, fluxo - signal.convolve(fluxo, np.ones(janela) / janela, mode="same"))
    if not fluxo.any():
        return 100, 0.0

    # Autocorrelacao do fluxo (via FFT)
    n = len(fluxo)
    espectro = np.fft.rfft(fluxo - fluxo.mean(), 2 * n)
    autocorr = np.fft.irfft(np.abs(espectro) ** 2)[:n]
    autocorr /= autocorr[0] + 1e-10

    def ac(lag):
        return np.interp(lag, np.arange(n), autocorr) if lag < n - 1 else 0.0

    melhor = (None, -np.inf)
    for bpm in np.arange(bpm_min, bpm_max + 0.01, 0.25):
        lag = 60.0 * taxa / bpm
        nota = ac(lag) + 0.5 * ac(2 * lag) + 0.25 * ac(4 * lag)
        # Preferencia leve por andamentos medios (evita metade/dobro)
        prior = np.exp(-0.5 * (np.log2(bpm / 105.0) / 0.8) ** 2)
        valor = nota * prior
        if valor > melhor[1]:
            melhor = (bpm, valor)
    bpm = float(melhor[0])

    # Fase: deslocamento que mais alinha os tempos com os ataques
    periodo = 60.0 * taxa / bpm
    melhor_fase = (0.0, -np.inf)
    for desloc in np.arange(0, periodo, 1.0):
        pos = np.arange(desloc, n, periodo).astype(int)
        valor = fluxo[pos].sum()
        if valor > melhor_fase[1]:
            melhor_fase = (desloc, valor)
    return int(round(bpm)), float(melhor_fase[0] / taxa)


# ----------------------------------------------------------------------------
# 3. Curva de afinacao -> notas limpas
# ----------------------------------------------------------------------------

def notas_de_f0(f0, voiced_prob, dt, ataques=None, confianca_min=0.35,
                histerese=0.7, quadros_firmes=3, duracao_min=0.09):
    """Converte a curva de frequencia (Hz por quadro) em notas.

    - Preenche falhas de 1-2 quadros no meio de uma nota.
    - Filtro de mediana: remove picos isolados de deteccao.
    - Histerese: so troca de nota quando a afinacao sai mais de 0,7
      semitom da nota atual por alguns quadros seguidos (vibrato e
      pequenas desafinacoes nao viram notas novas).
    - Notas muito curtas (deslizes entre notas) sao absorvidas.
    - Corrige saltos de oitava falsos (erro classico de deteccao).
    - Separa notas repetidas na mesma altura quando ha um ataque claro.

    Retorna lista de dicts: {"midi", "inicio", "fim", "confianca"} em
    altura de CONCERTO (som real)."""
    f0 = np.asarray(f0, dtype=float)
    prob = np.nan_to_num(np.asarray(voiced_prob, dtype=float))
    valido = (~np.isnan(f0)) & (f0 > 0) & (prob >= confianca_min)
    midi = np.full(len(f0), np.nan)
    midi[valido] = 69 + 12 * np.log2(f0[valido] / 440.0)

    # Preenche buracos de 1 quadro entre trechos de altura parecida (falha
    # de deteccao); buracos maiores costumam ser a separacao de notas repetidas
    i = 0
    n = len(midi)
    while i < n:
        if np.isnan(midi[i]):
            j = i
            while j < n and np.isnan(midi[j]):
                j += 1
            if 0 < i and j < n and (j - i) <= 1 and abs(midi[i - 1] - midi[j]) < 1.0:
                midi[i:j] = np.linspace(midi[i - 1], midi[j], j - i + 2)[1:-1]
                prob[i:j] = np.minimum(prob[i - 1], prob[j])
            i = j
        else:
            i += 1

    notas = []
    i = 0
    while i < n:
        if np.isnan(midi[i]):
            i += 1
            continue
        j = i
        while j < n and not np.isnan(midi[j]):
            j += 1
        trecho = midi[i:j].copy()
        if len(trecho) >= 5:
            trecho = signal.medfilt(trecho, 5)
        notas.extend(_segmentar_trecho(trecho, prob[i:j], i, dt, histerese, quadros_firmes))
        i = j

    notas = _dividir_por_ataques(notas, ataques, dt, duracao_min)
    notas = _remover_curtas(notas, duracao_min)
    notas = _corrigir_oitavas(notas)
    notas = _juntar_iguais(notas)
    notas = _ajustar_inicios(notas, ataques, dt)
    return [
        {"midi": int(nt["midi"]), "inicio": round(nt["inicio"], 4),
         "fim": round(nt["fim"], 4), "confianca": round(nt["confianca"], 3)}
        for nt in notas
    ]


def _segmentar_trecho(trecho, prob, offset, dt, histerese, quadros_firmes):
    notas = []
    atual = int(round(trecho[0]))
    inicio = 0
    pendente = None  # (candidato, inicio_do_candidato)
    for k in range(1, len(trecho)):
        if abs(trecho[k] - atual) > histerese:
            cand = int(round(trecho[k]))
            if pendente is None or pendente[0] != cand:
                pendente = (cand, k)
            if k - pendente[1] + 1 >= quadros_firmes:
                notas.append((atual, inicio, pendente[1]))
                atual, inicio = cand, pendente[1]
                pendente = None
        else:
            pendente = None
    notas.append((atual, inicio, len(trecho)))

    saida = []
    for _alt, ini, fim in notas:
        valores = trecho[ini:fim]
        saida.append({
            "midi": int(round(np.median(valores))),
            "inicio": (offset + ini) * dt,
            "fim": (offset + fim) * dt,
            "confianca": float(np.mean(prob[ini:fim])),
            "ataque": ini == 0,
        })
    return saida


def _dividir_por_ataques(notas, ataques, dt, duracao_min):
    if ataques is None or not len(ataques):
        return notas
    ataques = np.asarray(ataques)
    limiar = ataques.mean() + 2.5 * ataques.std()
    saida = []
    for nt in notas:
        ini_q = int(round(nt["inicio"] / dt))
        fim_q = int(round(nt["fim"] / dt))
        margem = max(2, int(round(duracao_min / dt)))
        cortes = []
        k = ini_q + margem
        while k < fim_q - margem and k < len(ataques):
            if (ataques[k] > limiar and ataques[k] >= ataques[k - 1]
                    and ataques[k] >= ataques[min(k + 1, len(ataques) - 1)]):
                cortes.append(k)
                k += margem
            else:
                k += 1
        if not cortes:
            saida.append(nt)
            continue
        bordas = [ini_q] + cortes + [fim_q]
        for a, b in zip(bordas[:-1], bordas[1:]):
            novo = dict(nt)
            novo["inicio"], novo["fim"] = a * dt, b * dt
            novo["ataque"] = True
            saida.append(novo)
    return saida


def _ajustar_inicios(notas, ataques, dt, recuo_max=0.35):
    """O detector de afinacao so 'firma' a nota alguns instantes depois do
    ataque (principalmente quando bateria/acordes batem junto). Puxamos o
    inicio de volta para o ataque mais forte logo antes, sem invadir a nota
    anterior - isso deixa o ritmo bem mais fiel na hora de encaixar no
    compasso."""
    if ataques is None or not len(ataques):
        return notas
    ataques = np.asarray(ataques)
    limiar = ataques.mean() + 1.0 * ataques.std()
    for k, nt in enumerate(notas):
        if not nt.get("ataque"):
            continue
        ini_q = int(round(nt["inicio"] / dt))
        limite = ini_q - int(recuo_max / dt)
        if k > 0:
            limite = max(limite, int(np.ceil(notas[k - 1]["fim"] / dt)))
        limite = max(0, limite)
        if limite >= ini_q or ini_q >= len(ataques):
            continue
        janela = ataques[limite:ini_q + 1]
        j = int(np.argmax(janela))
        if janela[j] > limiar:
            nt["inicio"] = (limite + j) * dt
    return notas


def _remover_curtas(notas, duracao_min):
    """Notas mais curtas que duracao_min geralmente sao o 'deslize' da voz
    entre duas notas: a nota anterior colada absorve o tempo dela."""
    saida = []
    for nt in notas:
        dur = nt["fim"] - nt["inicio"]
        if dur >= duracao_min:
            saida.append(nt)
            continue
        if saida and nt["inicio"] - saida[-1]["fim"] < 0.04:
            saida[-1]["fim"] = nt["fim"]
    return saida


def _corrigir_oitavas(notas):
    """Nota curta que pula exatamente ~1 oitava em relacao as vizinhas e
    volta logo em seguida e quase sempre erro de deteccao: puxa de volta."""
    for k, nt in enumerate(notas):
        dur = nt["fim"] - nt["inicio"]
        if dur > 0.35:
            continue
        viz = []
        if k > 0 and nt["inicio"] - notas[k - 1]["fim"] < 0.6:
            viz.append(notas[k - 1]["midi"])
        if k + 1 < len(notas) and notas[k + 1]["inicio"] - nt["fim"] < 0.6:
            viz.append(notas[k + 1]["midi"])
        if not viz:
            continue
        ref = float(np.mean(viz))
        dif = nt["midi"] - ref
        if dif >= 10:
            nt["midi"] -= 12
        elif dif <= -10:
            nt["midi"] += 12
    return notas


def _juntar_iguais(notas):
    saida = []
    for nt in notas:
        if (saida and saida[-1]["midi"] == nt["midi"]
                and nt["inicio"] - saida[-1]["fim"] < 0.05 and not nt.get("ataque")):
            saida[-1]["fim"] = nt["fim"]
            continue
        saida.append(nt)
    return saida
