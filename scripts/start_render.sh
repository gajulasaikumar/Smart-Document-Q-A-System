#!/bin/sh
set -eu

PORT_VALUE="${PORT:-10000}"
WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-1}"

celery -A app.core.celery_app.celery_app worker --loglevel=INFO --concurrency="$WORKER_CONCURRENCY" &
worker_pid="$!"

cleanup() {
  kill "$worker_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

uvicorn app.main:app --host 0.0.0.0 --port "$PORT_VALUE" &
api_pid="$!"

wait "$api_pid"
