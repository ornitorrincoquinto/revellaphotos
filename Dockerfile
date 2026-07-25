FROM python:3.11-slim

# Dependências de sistema necessárias para compilar o dlib (usado pelo
# reconhecimento facial). A primeira build demora vários minutos por causa
# dessa compilação — é normal, só acontece uma vez (fica em cache depois).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend

# Pasta onde as fotos ficam salvas. Em produção, monte um Volume persistente
# nesse caminho (ver README) — senão as fotos somem a cada novo deploy.
RUN mkdir -p /app/media
ENV MEDIA_ROOT=/app/media

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
