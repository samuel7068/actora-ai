# syntax=docker/dockerfile:1.6

# ---------- builder ----------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry==2.2.1"

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root && rm -rf "$POETRY_CACHE_DIR"

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . .

# 루트의 TASK_SHARE.md 를 컨테이너 안에 복사 (관리자 API 가 읽음)
# build context 는 ./backend 이므로 dockerfile 에서 상위 접근 불가 — entrypoint 에서 처리하거나 docker-compose 로 mount
# (대신 docker-compose 에서 read-only volume 마운트로 처리)

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
