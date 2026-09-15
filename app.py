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
import os

from flask import Flask, Response, render_template, request

import sax_core
import pdf_export

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/transcrever", methods=["POST"])
def transcrever():
    dados = request.get_json(force=True, silent=True) or {}
    origem = (dados.get("origem") or "").strip()

    def gerar():
        if not origem:
            yield json.dumps({"tipo": "erro", "mensagem": "Cole um link do YouTube ou digite o nome da musica."}) + "\n"
            return
        try:
            for evento in sax_core.processar_stream(origem):
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        except Exception as exc:  # protege o worker de qualquer falha inesperada
            yield json.dumps({"tipo": "erro", "mensagem": f"Erro inesperado: {exc}"}, ensure_ascii=False) + "\n"

    return Response(gerar(), mimetype="application/x-ndjson")


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


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    modo_debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=porta, debug=modo_debug)
