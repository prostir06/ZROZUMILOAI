# Build stage: компіляція залежностей без залишку gcc у runtime-образі.
FROM python:3.15-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
COPY requirements.lock* ./
RUN if [ -f requirements.lock ]; then \
      pip install --no-cache-dir -r requirements.lock; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

# Runtime stage
FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser . .

RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
