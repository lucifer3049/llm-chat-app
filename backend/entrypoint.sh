#!/usr/bin/env sh
# Container entrypoint: migrate -> seed -> serve (PLAN §3.4).
# Fail fast on any error so a broken migration/seed never serves traffic.
set -eu

echo "[entrypoint] Running database migrations..."
alembic upgrade head

# super_admin idempotent seed (invariant I-1). Added in Day 2; guarded so the
# Day 1 skeleton still boots before the seed module exists.
if python -c "import app.infrastructure.seed" 2>/dev/null; then
  echo "[entrypoint] Seeding super_admin..."
  python -m app.infrastructure.seed
fi

echo "[entrypoint] Starting gunicorn..."
exec gunicorn app.wsgi:app -c gunicorn.conf.py
