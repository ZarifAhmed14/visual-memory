FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV EVM_DATA_DIR=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY tools ./tools
COPY documents ./documents
COPY data ./data

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /data/runs /data/videos /data/videos/uploads

EXPOSE 8000

CMD ["uvicorn", "evm.web:app", "--host", "0.0.0.0", "--port", "8000"]
