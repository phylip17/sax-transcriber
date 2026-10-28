"""
partitura.py

Transforma as notas detectadas (altura de concerto + tempo em segundos) numa
partitura de verdade para Sax Alto em Mib:

- encaixa as notas no compasso (quantizacao na grade de colcheia ou
  semicolcheia, a partir do BPM detectado);
- escolhe onde cai o "tempo 1" do compasso;
- transpoe para Mib (+9 semitons) e ajusta a oitava para a extensao do sax;
- escolhe armadura de clave, grafia (sustenidos/bemois) e acidentes;
- quebra as figuras de forma legivel (ligaduras na barra e no meio do
  compasso, colcheias agrupadas por tempo);
- gera MusicXML, que vira PDF/PNG (render_partitura.py) e tambem abre no
  MuseScore, Flat, Sibelius etc. para corrigir alguma nota.
"""

from xml.sax.saxutils import escape

TRANSPOSICAO_SAX_ALTO = 9          # escrito = concerto + 9 semitons
ALCANCE_MIN = 58                   # Bb3 escrito
ALCANCE_MAX = 90                   # F#6 escrito
CENTRO_CONFORTAVEL = 70            # Bb4: meio da regiao mais confortavel

NOMES_SUSTENIDO = [("C", 0), ("C", 1), ("D", 0), ("D", 1), ("E", 0), ("F", 0),
                   ("F", 1), ("G", 0), ("G", 1), ("A", 0), ("A", 1), ("B", 0)]
NOMES_BEMOL = [("C", 0), ("D", -1), ("D", 0), ("E", -1), ("E", 0), ("F", 0),
               ("G", -1), ("G", 0), ("A", -1), ("A", 0), ("B", -1), ("B", 0)]
ORDEM_SUSTENIDOS = ["F", "C", "G", "D", "A", "E", "B"]
ORDEM_BEMOIS = ["B", "E", "A", "D", "G", "C", "F"]
# Tonica (classe de nota) de tom MAIOR -> numero de acidentes na armadura
QUINTAS_MAIOR = {0: 0, 7: 1, 2: 2, 9: 3, 4: 4, 11: 5, 6: 6,
                 5: -1, 10: -2, 3: -3, 8: -4, 1: -5}
NOMES_TOM_PT = {0: "Dó", 1: "Réb", 2: "Ré", 3: "Mib", 4: "Mi", 5: "Fá",
                6: "Fá#", 7: "Sol", 8: "Láb", 9: "Lá", 10: "Sib", 11: "Si"}
NOMES_TOM_PT_SUST = {1: "Dó#", 3: "Ré#", 6: "Fá#", 8: "Sol#", 10: "Lá#"}

NOMES_PT = {"C": "Dó", "D": "Ré", "E": "Mi", "F": "Fá", "G": "Sol", "A": "Lá", "B": "Si"}

# Figuras possiveis em "quarter lengths" (semínima = 1)
FIGURAS = [(4.0, "whole", 0), (3.0, "half", 1), (2.0, "half", 0),
           (1.5, "quarter", 1), (1.0, "quarter", 0), (0.75, "eighth", 1),
           (0.5, "eighth", 0), (0.25, "16th", 0)]


# ----------------------------------------------------------------------------
# Tonalidade
# ----------------------------------------------------------------------------

def armadura_escrita(tonica_concerto, modo):
    """Recebe a tonica da musica (classe 0-11, em concerto) e o modo
    ('maior'/'menor'). Retorna (quintas, tonica_escrita, nome_do_tom_escrito)."""
    tonica_escrita = (tonica_concerto + TRANSPOSICAO_SAX_ALTO) % 12
    relativa_maior = tonica_escrita if modo == "maior" else (tonica_escrita + 3) % 12
    quintas = QUINTAS_MAIOR[relativa_maior]
    if quintas > 0 and tonica_escrita in NOMES_TOM_PT_SUST:
        nome = NOMES_TOM_PT_SUST[tonica_escrita]
    else:
        nome = NOMES_TOM_PT[tonica_escrita]
    return quintas, tonica_escrita, f"{nome} {modo}"


def grafar(midi, quintas):
    """Nota MIDI -> (step, alter, octave), escolhendo sustenido ou bemol
    conforme a armadura."""
    tabela = NOMES_SUSTENIDO if quintas >= 0 else NOMES_BEMOL
    step, alter = tabela[midi % 12]
    return step, alter, midi // 12 - 1


def nome_pt(step, alter):
    """Nome da nota em portugues, como se le na partitura: Dó, Fá#, Sib..."""
    return NOMES_PT[step] + ("#" if alter > 0 else ("b" if alter < 0 else ""))


def nome_nota(midi, quintas=0):
    step, alter, octave = grafar(midi, quintas)
    return f"{step}{'#' if alter > 0 else ('b' if alter < 0 else '')}{octave}"


def _alteracoes_armadura(quintas):
    if quintas >= 0:
        return {s: 1 for s in ORDEM_SUSTENIDOS[:quintas]}
    return {s: -1 for s in ORDEM_BEMOIS[:-quintas]}


# ----------------------------------------------------------------------------
# Quantizacao
# ----------------------------------------------------------------------------

def quantizar(notas, bpm, fase_s, unidades_por_tempo, tempos_por_compasso):
    """Converte notas em segundos para posicoes inteiras na grade.
    Retorna lista de dicts {"midi", "ini", "fim"} (em unidades da grade),
    ja alinhada para o compasso comecar em 0."""
    if not notas:
        return []
    g = unidades_por_tempo
    dur_tempo = 60.0 / bpm
    latencia = 0.03  # o detector de afinacao reage uns ~30 ms depois do ataque
    eventos = []
    ultimo_ini = None
    for nt in sorted(notas, key=lambda n: n["inicio"]):
        b_ini = (nt["inicio"] - latencia - fase_s) / dur_tempo
        b_fim = (nt["fim"] - fase_s) / dur_tempo
        ini = _encaixar(b_ini, g, minimo=None if ultimo_ini is None else ultimo_ini + 1)
        fim = _encaixar(b_fim, g, minimo=ini + 1)
        eventos.append({"midi": nt["midi"], "ini": ini, "fim": fim,
                        "conf": nt.get("confianca", 1.0)})
        ultimo_ini = ini

    # Resolve sobreposicoes criadas pelo arredondamento
    limpos = []
    for ev in eventos:
        if limpos and ev["ini"] < limpos[-1]["fim"]:
            ant = limpos[-1]
            if ev["ini"] <= ant["ini"]:
                # Mesmo ponto de inicio: fica a nota mais longa/confiavel
                if (ev["fim"] - ev["ini"]) * ev["conf"] > (ant["fim"] - ant["ini"]) * ant["conf"]:
                    limpos[-1] = ev
                continue
            ant["fim"] = ev["ini"]
        limpos.append(ev)

    # Fecha buracos menores que 1 tempo: o detector costuma "encurtar" as
    # notas, e pausinhas no meio da frase so poluem a leitura. Pausas de
    # 1 tempo ou mais (respiracao, fim de frase) continuam na partitura.
    for a, b in zip(limpos[:-1], limpos[1:]):
        if 0 < b["ini"] - a["fim"] < g:
            a["fim"] = b["ini"]

    # Junta notas iguais coladas que viraram picadinhas no arredondamento
    juntos = []
    for ev in limpos:
        if (juntos and juntos[-1]["midi"] == ev["midi"] and juntos[-1]["fim"] == ev["ini"]
                and (ev["fim"] - ev["ini"]) == 1 and g >= 4):
            juntos[-1]["fim"] = ev["fim"]
            continue
        juntos.append(ev)

    # Escolhe onde fica o tempo 1: notas longas tendem a cair nos tempos fortes
    m = g * tempos_por_compasso
    melhor = (0, -1.0)
    for desloc_tempos in range(tempos_por_compasso):
        d = desloc_tempos * g
        pontos = 0.0
        for ev in juntos:
            pos = (ev["ini"] + d) % m
            dur = ev["fim"] - ev["ini"]
            if pos == 0:
                pontos += 2.0 * dur
            elif tempos_por_compasso == 4 and pos == m // 2:
                pontos += 1.0 * dur
            elif pos % g == 0:
                pontos += 0.3 * dur
        if pontos > melhor[1]:
            melhor = (d, pontos)
    desloc = melhor[0]
    primeiro = juntos[0]["ini"] + desloc
    base = (primeiro // m) * m
    for ev in juntos:
        ev["ini"] += desloc - base
        ev["fim"] += desloc - base
    return juntos


def _encaixar(b, g, minimo=None):
    """Encaixa uma posicao (em tempos) na grade, preferindo as posicoes mais
    'redondas': primeiro o tempo, depois a colcheia, por ultimo a
    semicolcheia. Assim um ataque um pouco atrasado vira seminima no tempo
    em vez de virar semicolcheia pontuada - a leitura fica muito mais limpa.
    minimo: menor posicao aceita (para nao colar duas notas no mesmo ponto)."""
    niveis = [(1, 0.28)]                       # tempo inteiro
    if g >= 2:
        niveis.append((2, 0.16))               # colcheia
    if g >= 4:
        niveis.append((4, 1.0))                # semicolcheia (sempre serve)
    else:
        niveis[-1] = (niveis[-1][0], 1.0)
    for sub, tolerancia in niveis:
        pos = round(b * sub)
        if abs(b * sub - pos) / sub <= tolerancia or tolerancia >= 1.0:
            unidades = pos * (g // sub)
            if minimo is None or unidades >= minimo:
                return unidades
    unidades = round(b * g)
    return unidades if minimo is None else max(unidades, minimo)


def ajustar_oitava(midis_escritos):
    """Desloca a melodia inteira em oitavas para caber o maximo possivel na
    extensao do sax alto; depois dobra as notas que ainda sobrarem fora."""
    if not midis_escritos:
        return 0, []
    melhor = None
    for k in (-24, -12, 0, 12, 24):
        dentro = sum(ALCANCE_MIN <= m + k <= ALCANCE_MAX for m in midis_escritos)
        ordenados = sorted(m + k for m in midis_escritos)
        mediana = ordenados[len(ordenados) // 2]
        chave = (dentro, -abs(mediana - CENTRO_CONFORTAVEL))
        if melhor is None or chave > melhor[0]:
            melhor = (chave, k)
    k = melhor[1]
    saida = []
    for m in midis_escritos:
        m += k
        while m < ALCANCE_MIN:
            m += 12
        while m > ALCANCE_MAX:
            m -= 12
        saida.append(m)
    return k, saida


# ----------------------------------------------------------------------------
# Divisao em figuras legiveis
# ----------------------------------------------------------------------------

def _figuras_em_unidades(g):
    figs = []
    for ql, tipo, pontos in FIGURAS:
        u = ql * g
        if abs(u - round(u)) < 1e-9 and u >= 1:
            figs.append((int(round(u)), tipo, pontos))
    return figs


def _decompor(pos, dur, g, tempos, eh_pausa):
    """Quebra uma duracao (dentro de UM compasso) em figuras, respeitando
    os tempos: nota fora do tempo nao atravessa o proximo tempo, e no 4/4
    nada que comeca nos tempos 2 ou 4 atravessa o meio do compasso."""
    figs = _figuras_em_unidades(g)
    m = g * tempos
    partes = []
    while dur > 0:
        limite = dur
        no_tempo = pos % g == 0
        if not no_tempo:
            limite = min(limite, g - pos % g)
        else:
            limite = min(limite, m - pos)
            if tempos == 4 and pos % (2 * g) != 0:
                limite = min(limite, 2 * g - pos % (2 * g))
            if eh_pausa:
                # Pausas: inteira so no compasso todo; minima so na metade
                if not (pos == 0 and dur >= m):
                    if tempos == 4 and pos % (2 * g) == 0 and dur >= 2 * g:
                        limite = min(limite, 2 * g)
                    else:
                        limite = min(limite, g)
        escolha = None
        for u, tipo, pontos in figs:
            if u <= limite:
                if eh_pausa and pontos:
                    continue  # pausas pontuadas atrapalham a leitura
                escolha = (u, tipo, pontos)
                break
        if escolha is None:
            escolha = figs[-1]
        partes.append((pos, escolha[0], escolha[1], escolha[2]))
        pos += escolha[0]
        dur -= escolha[0]
    return partes


# ----------------------------------------------------------------------------
# Montagem
# ----------------------------------------------------------------------------

def montar(notas_concerto, bpm, fase_s, tonica, modo, detalhe="semicolcheia",
           tempos_por_compasso=4, titulo="Transcrição", ajuste_oitava_manual=0,
           nomes_das_notas=True):
    """Pipeline completo: notas (concerto, segundos) -> partitura.
    Retorna dict com musicxml, lista de notas escritas e metadados."""
    g = 4 if detalhe == "semicolcheia" else 2
    eventos = quantizar(notas_concerto, bpm, fase_s, g, tempos_por_compasso)
    quintas, tonica_escrita, nome_tom = armadura_escrita(tonica, modo)

    escritos = [ev["midi"] + TRANSPOSICAO_SAX_ALTO for ev in eventos]
    desloc, escritos = ajustar_oitava(escritos)
    if ajuste_oitava_manual:
        escritos = [m + 12 * ajuste_oitava_manual for m in escritos]
    for ev, m in zip(eventos, escritos):
        ev["escrito"] = m

    compassos = _organizar_compassos(eventos, g, tempos_por_compasso)
    xml = _gerar_musicxml(compassos, g, tempos_por_compasso, quintas, modo, bpm, titulo, nome_tom,
                          nomes_das_notas)

    # Frases (para a parte de letra/pratica do app): quebra em pausas >= 1 tempo
    frases, atual = [], []
    for k, ev in enumerate(eventos):
        if k and ev["ini"] - eventos[k - 1]["fim"] >= g and atual:
            frases.append(atual)
            atual = []
        atual.append(nome_nota(ev["escrito"], 0))
    if atual:
        frases.append(atual)

    return {
        "musicxml": xml,
        # Nomes sempre com sustenido para a lista simples (compatibilidade
        # com o resto do app); a partitura usa a grafia correta do tom.
        "notas": [nome_nota(m, 0) for m in escritos],
        "frases": frases,
        "confiancas": [round(ev["conf"], 2) for ev in eventos],
        "notas_escritas": [nome_nota(m, quintas) for m in escritos],
        "tom_escrito": nome_tom,
        "quintas": quintas,
        "compassos": len(compassos),
        "bpm": bpm,
        "fora_do_alcance": [not (ALCANCE_MIN <= m <= ALCANCE_MAX) for m in escritos],
    }


def _organizar_compassos(eventos, g, tempos):
    """Distribui notas e pausas pelos compassos, cortando (com ligadura) o
    que atravessa a barra de compasso."""
    m = g * tempos
    if not eventos:
        return [[(0, m, None, None)]]
    fim_total = eventos[-1]["fim"]
    n_compassos = (fim_total + m - 1) // m
    compassos = [[] for _ in range(n_compassos)]

    linha = []  # (ini, fim, midi_escrito) incluindo pausas
    cursor = 0
    for ev in eventos:
        if ev["ini"] > cursor:
            linha.append((cursor, ev["ini"], None))
        linha.append((ev["ini"], ev["fim"], ev["escrito"]))
        cursor = ev["fim"]
    if cursor < n_compassos * m:
        linha.append((cursor, n_compassos * m, None))

    for ini, fim, alt in linha:
        pos = ini
        while pos < fim:
            c = pos // m
            fim_trecho = min(fim, (c + 1) * m)
            liga_antes = alt is not None and pos > ini
            liga_depois = alt is not None and fim_trecho < fim
            compassos[c].append((pos - c * m, fim_trecho - pos, alt, (liga_antes, liga_depois)))
            pos = fim_trecho
    return compassos


def _gerar_musicxml(compassos, g, tempos, quintas, modo, bpm, titulo, nome_tom,
                    nomes_das_notas=True):
    alter_armadura = _alteracoes_armadura(quintas)
    m_total = g * tempos
    saida = []
    w = saida.append
    w('<?xml version="1.0" encoding="UTF-8"?>')
    w('<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
      '"http://www.musicxml.org/dtds/partwise.dtd">')
    w('<score-partwise version="3.1">')
    w(f'<work><work-title>{escape(titulo)}</work-title></work>')
    w('<identification><creator type="arranger">Transcrição automática - Sax Alto (Mib)</creator>'
      '<encoding><software>sax-transcriber</software></encoding></identification>')
    w('<part-list><score-part id="P1"><part-name>Sax Alto (Mib)</part-name>'
      '<part-abbreviation>A. Sax.</part-abbreviation></score-part></part-list>')
    w('<part id="P1">')

    # Quebra de linha pela quantidade de notas: com os nomes escritos
    # embaixo, cada nota precisa de espaco para o nome nao encavalar.
    limite_linha = 14 if nomes_das_notas else 22
    contagem_linha = 0
    for num, itens in enumerate(compassos, start=1):
        n_notas = len(itens)  # notas, pausas e continuacoes ligadas: tudo ocupa espaco
        nova_linha = num > 1 and contagem_linha + n_notas > limite_linha
        contagem_linha = n_notas if (nova_linha or num == 1) else contagem_linha + n_notas
        w(f'<measure number="{num}">')
        if nova_linha:
            w('<print new-system="yes"/>')
        if num == 1:
            w(f'<attributes><divisions>{g}</divisions>'
              f'<key><fifths>{quintas}</fifths><mode>{"major" if modo == "maior" else "minor"}</mode></key>'
              f'<time><beats>{tempos}</beats><beat-type>4</beat-type></time>'
              '<clef><sign>G</sign><line>2</line></clef></attributes>')
            # Andamento em texto simples (o simbolo de seminima depende de uma
            # fonte especial que nem todo conversor de PDF tem)
            w('<direction placement="above"><direction-type>'
              f'<words font-weight="bold">Andamento: {bpm} bpm  |  Tom escrito: {escape(nome_tom)}</words>'
              f'</direction-type><sound tempo="{bpm}"/></direction>')

        estado = {}  # (step, octave) -> alter vigente neste compasso
        pecas = []
        for pos, dur, alt, ligas in itens:
            eh_pausa = alt is None
            if eh_pausa and pos == 0 and dur == m_total:
                pecas.append({"pausa_compasso": True, "dur": dur})
                continue
            partes = _decompor(pos, dur, g, tempos, eh_pausa)
            for k, (p, u, tipo, pontos) in enumerate(partes):
                peca = {"pos": p, "dur": u, "tipo": tipo, "pontos": pontos, "midi": alt}
                if not eh_pausa:
                    liga_ini = ligas[0] or k > 0
                    liga_fim = ligas[1] or k < len(partes) - 1
                    peca["tie_stop"] = liga_ini
                    peca["tie_start"] = liga_fim
                pecas.append(peca)

        _marcar_barras(pecas, g)

        for peca in pecas:
            if peca.get("pausa_compasso"):
                w(f'<note><rest measure="yes"/><duration>{peca["dur"]}</duration><voice>1</voice></note>')
                continue
            if peca["midi"] is None:
                w(f'<note><rest/><duration>{peca["dur"]}</duration><voice>1</voice>'
                  f'<type>{peca["tipo"]}</type>{"<dot/>" * peca["pontos"]}</note>')
                continue
            step, alt, octave = grafar(peca["midi"], quintas)
            vigente = estado.get((step, octave), alter_armadura.get(step, 0))
            acidente = ""
            if peca["tie_stop"]:
                pass  # nota ligada nao repete acidente
            elif alt != vigente:
                acidente = {1: "sharp", -1: "flat", 0: "natural"}[alt]
                estado[(step, octave)] = alt
            partes_xml = ['<note><pitch>', f'<step>{step}</step>']
            if alt:
                partes_xml.append(f'<alter>{alt}</alter>')
            partes_xml.append(f'<octave>{octave}</octave></pitch><duration>{peca["dur"]}</duration>')
            if peca["tie_stop"]:
                partes_xml.append('<tie type="stop"/>')
            if peca["tie_start"]:
                partes_xml.append('<tie type="start"/>')
            partes_xml.append(f'<voice>1</voice><type>{peca["tipo"]}</type>')
            partes_xml.append("<dot/>" * peca["pontos"])
            if acidente:
                partes_xml.append(f'<accidental>{acidente}</accidental>')
            for nivel, valor in peca.get("beams", []):
                partes_xml.append(f'<beam number="{nivel}">{valor}</beam>')
            if peca["tie_stop"] or peca["tie_start"]:
                partes_xml.append('<notations>')
                if peca["tie_stop"]:
                    partes_xml.append('<tied type="stop"/>')
                if peca["tie_start"]:
                    partes_xml.append('<tied type="start"/>')
                partes_xml.append('</notations>')
            if nomes_das_notas and not peca["tie_stop"]:
                # Nome da nota escrito embaixo dela (so no inicio da nota;
                # a continuacao ligada nao repete o nome)
                partes_xml.append('<lyric number="1" placement="below"><syllabic>single</syllabic>'
                                  f'<text>{nome_pt(step, alt)}</text></lyric>')
            partes_xml.append('</note>')
            w("".join(partes_xml))
        if num == len(compassos):
            w('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
        w('</measure>')
    w('</part></score-partwise>')
    return "\n".join(saida)


def _marcar_barras(pecas, g):
    """Agrupa colcheias/semicolcheias seguidas dentro do mesmo tempo."""
    curtas = {"eighth", "16th"}
    grupo = []

    def fechar():
        if len(grupo) >= 2:
            for k, pc in enumerate(grupo):
                if k == 0:
                    b1 = "begin"
                elif k == len(grupo) - 1:
                    b1 = "end"
                else:
                    b1 = "continue"
                beams = [(1, b1)]
                if pc["tipo"] == "16th":
                    ant = k > 0 and grupo[k - 1]["tipo"] == "16th"
                    prox = k < len(grupo) - 1 and grupo[k + 1]["tipo"] == "16th"
                    if ant and prox:
                        beams.append((2, "continue"))
                    elif prox:
                        beams.append((2, "begin"))
                    elif ant:
                        beams.append((2, "end"))
                    else:
                        beams.append((2, "forward hook" if k == 0 else "backward hook"))
                pc["beams"] = beams
        grupo.clear()

    tempo_atual = None
    for pc in pecas:
        if pc.get("pausa_compasso"):
            fechar()
            continue
        tempo = pc["pos"] // g
        if pc["midi"] is None or pc["tipo"] not in curtas:
            fechar()
            tempo_atual = None
            continue
        if tempo != tempo_atual:
            fechar()
            tempo_atual = tempo
        grupo.append(pc)
    fechar()
