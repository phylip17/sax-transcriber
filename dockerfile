# Imagem base enxuta com Python
FROM python:3.11-slim

# FFmpeg e necessario para o yt-dlp extrair audio e para o librosa ler o arquivo.
# Node.js e necessario para o yt-dlp resolver desafios em JavaScript que o
# YouTube passou a exigir para liberar o link real do audio.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia so o requirements primeiro (acelera builds futuros com cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do projeto
COPY . .

# O Render define a variavel PORT automaticamente; usamos 10000 como padrao local
ENV PORT=10000
EXPOSE 10000

# --timeout alto porque analisar a melodia de uma musica pode levar 1-2 minutos
# --workers 1 --threads 1 porque o plano gratuito do Render tem so 512MB de RAM;
# rodar so uma analise de audio por vez evita estourar a memoria disponivel
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 1 --timeout 300
