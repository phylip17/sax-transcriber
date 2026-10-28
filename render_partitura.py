"""
render_partitura.py

Desenha a partitura (MusicXML) com o Verovio - o mesmo motor de gravacao
musical usado por bibliotecas digitais de partituras - e converte para PDF
(A4, varias paginas) e PNG (uma imagem so, boa para abrir no celular).

Dependencias no servidor:
  - pip: verovio, pypdf, Pillow
  - apt: librsvg2-bin (comando rsvg-convert, converte SVG -> PDF/PNG)
"""

import io
import os
import shutil
import subprocess
import tempfile

# Pagina na proporcao A4. Uma pagina "menor" em unidades do Verovio deixa a
# pauta maior quando a pagina e esticada para A4 (mais facil de ler na estante)
OPCOES_VEROVIO = {
    "pageWidth": 1500,
    "pageHeight": 2121,
    "pageMarginTop": 60,
    "pageMarginBottom": 60,
    "pageMarginLeft": 60,
    "pageMarginRight": 60,
    "scale": 58,
    "breaks": "encoded",   # quebras de linha decididas em partitura.py
    "lyricSize": 3.6,
    "header": "auto",
    "footer": "none",
    "spacingSystem": 14,
    "spacingStaff": 12,
    "adjustPageHeight": False,
    "font": "Leipzig",
}

# A4 em pixels a 96 dpi (o rsvg-convert usa isso para PDF tambem)
A4_PX = (794, 1123)
LARGURA_PNG = 1400


def _kebab(nome):
    return "".join("-" + c.lower() if c.isupper() else c for c in nome)


def renderizar_svgs(musicxml, opcoes_extra=None):
    """Retorna a lista de paginas da partitura, cada uma como texto SVG."""
    opcoes = dict(OPCOES_VEROVIO)
    if opcoes_extra:
        opcoes.update(opcoes_extra)

    try:
        import verovio  # pacote pip
    except ImportError:
        verovio = None

    if verovio is not None:
        tk = verovio.toolkit()
        try:
            tk.setOptions(opcoes)
        except TypeError:  # versoes antigas so aceitam texto JSON
            import json
            tk.setOptions(json.dumps(opcoes))
        if not tk.loadData(musicxml):
            raise RuntimeError("O Verovio nao conseguiu ler a partitura gerada.")
        return [tk.renderToSVG(p) for p in range(1, tk.getPageCount() + 1)]

    # Alternativa: executavel de linha de comando do Verovio
    binario = shutil.which("verovio") or os.environ.get("VEROVIO_BIN")
    if not binario:
        raise RuntimeError("Verovio nao instalado (pip install verovio).")
    with tempfile.TemporaryDirectory() as pasta:
        entrada = os.path.join(pasta, "partitura.musicxml")
        with open(entrada, "w", encoding="utf-8") as f:
            f.write(musicxml)
        cmd = [binario, entrada, "-a", "-t", "svg", "-o", os.path.join(pasta, "pag.svg")]
        for chave, valor in opcoes.items():
            if isinstance(valor, bool):
                if valor:
                    cmd.append(f"--{_kebab(chave)}")
                continue
            cmd += [f"--{_kebab(chave)}", str(valor)]
        recursos = os.environ.get("VEROVIO_DATA")
        if recursos:
            cmd += ["-r", recursos]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Falha no Verovio: {res.stderr.strip()[-300:]}")
        paginas = sorted(p for p in os.listdir(pasta) if p.endswith(".svg"))
        saida = []
        for p in paginas:
            with open(os.path.join(pasta, p), encoding="utf-8") as f:
                saida.append(f.read())
        return saida


def _rsvg(svg_texto, formato, largura=None, altura=None):
    binario = shutil.which("rsvg-convert") or os.environ.get("RSVG_BIN")
    if not binario:
        raise RuntimeError("rsvg-convert nao instalado (apt install librsvg2-bin).")
    cmd = [binario, "-f", formato, "-b", "white", "-a"]
    if largura:
        cmd += ["-w", str(largura)]
    if altura:
        cmd += ["-h", str(altura)]
    res = subprocess.run(cmd, input=svg_texto.encode("utf-8"), capture_output=True)
    if res.returncode != 0:
        raise RuntimeError(f"Falha ao converter a partitura: {res.stderr.decode(errors='ignore')[-300:]}")
    return res.stdout


def svgs_para_pdf(svgs):
    from pypdf import PdfReader, PdfWriter

    escritor = PdfWriter()
    for svg in svgs:
        pdf = _rsvg(svg, "pdf", *A4_PX)
        for pagina in PdfReader(io.BytesIO(pdf)).pages:
            escritor.add_page(pagina)
    buffer = io.BytesIO()
    escritor.write(buffer)
    return buffer.getvalue()


def _recortar_branco(imagem, margem=40):
    from PIL import ImageChops, Image

    fundo = Image.new(imagem.mode, imagem.size, (255, 255, 255))
    caixa = ImageChops.difference(imagem, fundo).getbbox()
    if not caixa:
        return imagem
    x0, y0, x1, y1 = caixa
    return imagem.crop((0, max(0, y0 - margem), imagem.width, min(imagem.height, y1 + margem)))


def svgs_para_png(svgs):
    """Junta todas as paginas numa unica imagem PNG comprida (sem os
    espacos em branco do fim de cada pagina)."""
    from PIL import Image

    imagens = []
    for svg in svgs:
        png = _rsvg(svg, "png", LARGURA_PNG)
        img = Image.open(io.BytesIO(png)).convert("RGB")
        imagens.append(_recortar_branco(img))
    altura = sum(i.height for i in imagens)
    final = Image.new("RGB", (LARGURA_PNG, altura), (255, 255, 255))
    y = 0
    for img in imagens:
        final.paste(img, (0, y))
        y += img.height
    buffer = io.BytesIO()
    final.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()
