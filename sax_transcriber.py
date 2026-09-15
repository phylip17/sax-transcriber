#!/usr/bin/env python3
"""
sax_transcriber.py (modo terminal)

Baixa o audio de uma musica do YouTube (por link ou por busca) e extrai
a linha melodica principal, convertendo as notas para a versao "escrita"
do Sax Alto em Eb.

Uso:
    python sax_transcriber.py --url "https://youtube.com/watch?v=XXXX" --output notas.txt
    python sax_transcriber.py --search "Wave Tom Jobim" --output notas.txt

Dica: se preferir uma interface visual, rode "python app.py" e abra
http://127.0.0.1:5000 no navegador.
"""

import argparse
import sys

import sax_core


def main():
    parser = argparse.ArgumentParser(
        description="Extrai a melodia de uma musica do YouTube e gera as notas "
                     "transpostas para Sax Alto em Eb."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--url", help="Link direto do video no YouTube")
    grupo.add_argument("--search", help="Termo de busca (ex: 'Garota de Ipanema')")
    parser.add_argument("--output", default="notas_sax.txt", help="Arquivo de saida (texto)")
    args = parser.parse_args()

    origem = args.url or args.search
    notas_finais = None

    for evento in sax_core.processar_stream(origem):
        if evento["tipo"] == "log":
            print(f"[*] {evento['mensagem']}")
        elif evento["tipo"] == "erro":
            print(f"[!] {evento['mensagem']}")
            sys.exit(1)
        elif evento["tipo"] == "resultado":
            notas_finais = evento["notas"]

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(" ".join(notas_finais))

    print(f"[OK] {len(notas_finais)} notas salvas em: {args.output}")
    preview = " ".join(notas_finais[:20])
    print("Previa:", preview, "..." if len(notas_finais) > 20 else "")


if __name__ == "__main__":
    main()
