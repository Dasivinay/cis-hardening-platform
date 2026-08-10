#!/bin/sh
set -e

echo "[entrypoint] waiting for postgres..."

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

database_url = os.environ.get("DATABASE_URL")

if not database_url:
    print("[entrypoint] ERROR: DATABASE_URL is not set")
    raise SystemExit(1)

database_url = database_url.replace(
    "postgresql+psycopg2://",
    "postgresql://",
    1
)

parsed = urlparse(database_url)

host = parsed.hostname
port = parsed.port or 5432

if not host:
    print("[entrypoint] ERROR: Could not determine PostgreSQL host")
    raise SystemExit(1)

print(f"[entrypoint] checking postgres at {host}:{port}")

for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=3):
            print("[entrypoint] postgres is reachable")
            break
    except Exception as e:
        if attempt == 59:
            print(f"[entrypoint] ERROR: PostgreSQL connection failed: {e}")
            raise SystemExit(1)

        print(
            f"[entrypoint] postgres not ready, retrying... "
            f"({attempt + 1}/60)"
        )
        time.sleep(2)
else:
    raise SystemExit(1)

PY

echo "[entrypoint] running migrations..."

flask db upgrade

echo "[entrypoint] migrations completed"

echo "[entrypoint] seeding initial data..."

python seed.py || true

echo "[entrypoint] starting application..."

if [ "$#" -eq 0 ]; then
    exec gunicorn \
        --bind "0.0.0.0:${PORT:-5000}" \
        --workers 1 \
        --timeout 120 \
        wsgi:app
else
    exec "$@"
fi
