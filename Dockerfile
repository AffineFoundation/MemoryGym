FROM golang:1.22-bookworm AS affent-builder

ARG AFFENT_REPO=https://github.com/AffineFoundation/affent.git
ARG AFFENT_REF=main

RUN git init /src/affent \
    && cd /src/affent \
    && git remote add origin "${AFFENT_REPO}" \
    && git fetch --depth 1 origin "${AFFENT_REF}" \
    && git checkout --detach FETCH_HEAD \
    && go build -trimpath -ldflags="-s -w" -o /out/affentctl ./cmd/affentctl \
    && /out/affentctl run --help 2>&1 | grep -q -- "-memory-only" \
    || (echo "affentctl must support --memory-only; set AFFENT_REF to a memory-enabled affent ref" >&2; exit 1)

FROM python:3.11-slim

WORKDIR /app

COPY --from=affent-builder /out/affentctl /usr/local/bin/affentctl

# Copy and install Python deps
COPY pyproject.toml ./
COPY memorygym/ memorygym/
COPY env.py .

# Container eval defaults to affent + affent's Markdown memory files. Legacy
# stream-runner search backends are optional and intentionally not installed
# here because ChromaDB / sentence-transformers pull very large dependencies.
RUN pip install --no-cache-dir -e ".[affinetes]"

# Python should handle SIGTERM for graceful shutdown in container
ENV PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM

EXPOSE 8080
