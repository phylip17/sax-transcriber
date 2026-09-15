"""
pdf_export.py

Gera um PDF simples com a lista de notas (sem pauta musical), organizada
em uma grade legível, pronta para imprimir ou consultar no celular.
"""

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

NOTAS_POR_LINHA = 8


def _montar_tabela_de_notas(notas):
    linhas = []
    for i in range(0, len(notas), NOTAS_POR_LINHA):
        trecho = notas[i:i + NOTAS_POR_LINHA]
        trecho += [""] * (NOTAS_POR_LINHA - len(trecho))  # completa a última linha
        linhas.append(trecho)

    tabela = Table(linhas, colWidths=[20 * mm] * NOTAS_POR_LINHA)
    tabela.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("FONTSIZE", (0, 0), (-1, -1), 12),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1B2430")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#C9C2B3")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBF9F4")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return tabela


def gerar_pdf_notas(notas, titulo="Notas para Sax Alto (Eb)", origem=None):
    """Recebe uma lista de notas (ex: ['D4', 'E4', 'F#4', ...]) e retorna
    os bytes de um PDF pronto para download."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloCustom", parent=estilos["Title"],
        fontName="Helvetica-Bold", fontSize=20, alignment=TA_LEFT,
        textColor=colors.HexColor("#1B2430"), spaceAfter=4,
    )
    estilo_sub = ParagraphStyle(
        "SubCustom", parent=estilos["Normal"],
        fontName="Helvetica", fontSize=10.5,
        textColor=colors.HexColor("#6b665b"), spaceAfter=18,
    )
    estilo_rodape = ParagraphStyle(
        "RodapeCustom", parent=estilos["Normal"],
        fontName="Helvetica-Oblique", fontSize=8.5,
        textColor=colors.HexColor("#948d80"), spaceBefore=22,
    )

    elementos = [Paragraph(titulo, estilo_titulo)]

    linha_sub = f"{len(notas)} notas · transposição para Sax Alto em Eb"
    if origem:
        linha_sub += f" · {origem}"
    linha_sub += f" · gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elementos.append(Paragraph(linha_sub, estilo_sub))

    elementos.append(_montar_tabela_de_notas(notas))

    elementos.append(Paragraph(
        "Sequência de alturas aproximada, sem indicação de ritmo. Confira sempre ouvindo a música.",
        estilo_rodape,
    ))

    documento.build(elementos)
    buffer.seek(0)
    return buffer.read()
