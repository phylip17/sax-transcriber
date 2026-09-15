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
import shutil
import tempfile

from flask import Flask, Response, render_template, request
from werkzeug.utils import secure_filename

import sax_core
import pdf_export

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60 MB por upload


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
    pasta_tmp = tempfile.mkdtemp()
    nome_seguro = secure_filename(arquivo.filename) or "audio_enviado"
    caminho_salvo = os.path.join(pasta_tmp, nome_seguro)
    arquivo.save(caminho_salvo)

    def gerar():
        try:
            for evento in sax_core.processar_arquivo_stream(caminho_salvo):
                yield json.dumps(evento, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"tipo": "erro", "mensagem": f"Erro inesperado: {exc}"}, ensure_ascii=False) + "\n"
        finally:
            shutil.rmtree(pasta_tmp, ignore_errors=True)

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
