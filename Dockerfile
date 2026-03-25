FROM python:3.11-slim

WORKDIR /app

# Install system deps for chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY pyproject.toml setup.cfg* ./
COPY memorygym/ memorygym/
COPY env.py .

RUN pip install --no-cache-dir -e .

# Pre-download sentence-transformers model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Python should handle SIGTERM for graceful shutdown in container
ENV PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM

EXPOSE 8080
