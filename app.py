#!/usr/bin/env python3
"""
app.py

App web (Flask) para o Transcritor de Sax Alto. Pode rodar localmente
na sua maquina ou hospedado (ex: Render.com). Nada e enviado a
terceiros alem do proprio YouTube (para baixar o audio).

Uso local:
    python app.py
    Depois abra http://127.0.0.1:5000 no navegador.

Em producao (Render), quem inicia o servidor e o gunicorn (ver Dockerfile),
entao o bloco "if __name__" abaixo so roda no seu uso local.
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import traceback

from flask import Flask, Response, render_template, request
from werkzeug.utils import secure_filename

import re
import unicodedata

import sax_core
import pdf_export
import render_partitura

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60 MB por upload

logger = logging.getLogger("sax_transcriber")
logging.basicConfig(level=logging.INFO, stream=sys.stdout)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/transcrever", methods=["POST"])
def transcrever():
    dados = request.get_json(force=True, silent=True) or {}
    origem = (dados.get("origem") or "").strip()
    separar = bool(dados.get("separar_voz", True))

    def gerar():
        if not origem:
            yield json.dumps({"tipo": "erro", "mensagem": "Cole um link do YouTube ou digite o nome da musica."}) + "\n"
            return
        try:
            for evento in sax_core.processar_stream(origem, separar_voz=separar):
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        except Exception as exc:  # protege o worker de qualquer falha inesperada
            logger.error("Falha em /api/transcrever:\n%s", traceback.format_exc())
            yield json.dumps({"tipo": "erro", "mensagem": f"Erro inesperado: {exc}"}, ensure_ascii=False) + "\n"

    return Response(gerar(), mimetype="application/x-ndjson")


@app.route("/api/transcrever-arquivo", methods=["POST"])
def transcrever_arquivo():
    arquivo = request.files.get("arquivo")

    if arquivo is None or arquivo.filename == "":
        def gerar_erro():
            yield json.dumps({"tipo": "erro", "mensagem": "Nenhum arquivo de audio enviado."}) + "\n"
        return Response(gerar_erro(), mimetype="application/x-ndjson")

    # O arquivo precisa ser salvo AGORA, antes da resposta em streaming
    # comecar - o Flask fecha o arquivo enviado assim que a view retorna,
    # entao salvar dentro do gerador (que so roda durante o envio da
    # resposta) falha com "read of closed file".
    separar = request.form.get("separar_voz", "1") != "0"
    titulo = os.path.splitext(arquivo.filename)[0].replace("_", " ").strip()
    pasta_tmp = tempfile.mkdtemp()
    nome_seguro = secure_filename(arquivo.filename) or "audio_enviado"
    caminho_salvo = os.path.join(pasta_tmp, nome_seguro)
    arquivo.save(caminho_salvo)

    def gerar():
        try:
            for evento in sax_core.processar_arquivo_stream(caminho_salvo, separar_voz=separar, titulo=titulo):
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        except Exception as exc:
            logger.error("Falha em /api/transcrever-arquivo:\n%s", traceback.format_exc())
            yield json.dumps({"tipo": "erro", "mensagem": f"Erro inesperado: {exc}"}, ensure_ascii=False) + "\n"
        finally:
            shutil.rmtree(pasta_tmp, ignore_errors=True)

    return Response(gerar(), mimetype="application/x-ndjson")


def _nome_arquivo(titulo, extensao):
    base = unicodedata.normalize("NFKD", titulo or "partitura").encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", base).strip("_").lower() or "partitura"
    return f"{base[:60]}_sax_alto.{extensao}"


@app.route("/api/partitura", methods=["POST"])
def partitura_endpoint():
    """Refaz a partitura a partir das notas ja detectadas (sem reprocessar o
    audio), com novos ajustes, e devolve no formato pedido:
    svg (JSON para mostrar na tela), pdf, png ou musicxml."""
    corpo = request.get_json(force=True, silent=True) or {}
    dados = corpo.get("dados_brutos")
    opcoes = corpo.get("opcoes") or {}
    formato = (corpo.get("formato") or "svg").lower()
    if not dados or not dados.get("notas"):
        return Response("Nenhuma transcricao informada.", status=400)
    try:
        resultado = sax_core.gerar_partitura(dados, opcoes)
        titulo = opcoes.get("titulo") or dados.get("titulo") or "partitura"
        if formato == "pdf":
            conteudo = render_partitura.svgs_para_pdf(resultado["svgs"])
            tipo = "application/pdf"
        elif formato == "png":
            conteudo = render_partitura.svgs_para_png(resultado["svgs"])
            tipo = "image/png"
        elif formato == "musicxml":
            conteudo = resultado["musicxml"].encode("utf-8")
            tipo = "application/vnd.recordare.musicxml+xml"
        else:
            return Response(json.dumps({
                "svgs": resultado["svgs"],
                "tom_escrito": resultado["tom_escrito"],
                "compassos": resultado["compassos"],
                "bpm": resultado["bpm"],
                "notas": resultado["notas"],
                "frases": resultado["frases"],
                "confiancas": resultado["confiancas"],
                "fora_do_alcance": resultado["fora_do_alcance"],
            }, ensure_ascii=False), mimetype="application/json")
    except Exception as exc:
        logger.error("Falha em /api/partitura:\n%s", traceback.format_exc())
        return Response(f"Erro ao gerar a partitura: {exc}", status=500)

    extensao = "musicxml" if formato == "musicxml" else formato
    return Response(conteudo, mimetype=tipo, headers={
        "Content-Disposition": f'attachment; filename="{_nome_arquivo(titulo, extensao)}"'})


@app.route("/api/pdf", methods=["POST"])
def gerar_pdf():
    dados = request.get_json(force=True, silent=True) or {}
    notas = dados.get("notas") or []
    origem = (dados.get("origem") or "").strip() or None

    if not notas:
        return Response("Nenhuma nota informada.", status=400)

    pdf_bytes = pdf_export.gerar_pdf_notas(notas, origem=origem)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=notas_sax.pdf"},
    )


@app.route("/api/pdf-letra", methods=["POST"])
def gerar_pdf_letra():
    dados = request.get_json(force=True, silent=True) or {}
    grupos = dados.get("grupos") or []
    origem = (dados.get("origem") or "").strip() or None

    if not grupos:
        return Response("Nenhum grupo de notas/letra informado.", status=400)

    pdf_bytes = pdf_export.gerar_pdf_com_letra(grupos, origem=origem)

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=notas_com_letra.pdf"},
    )


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    modo_debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=porta, debug=modo_debug)
