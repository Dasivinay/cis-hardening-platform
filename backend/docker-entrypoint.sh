#!/bin/sh
set -e

echo "[entrypoint] waiting for postgres..."
until python -c "
import socket, os, sys
host = os.environ.get('POSTGRES_HOST', 'db')
port = int(os.environ.get('POSTGRES_PORT', 5432))
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
try:
    s.connect((host, port))
    s.close()
except Exception:
    sys.exit(1)
"; do
  sleep 1
done

echo "[entrypoint] running migrations..."
flask db upgrade || flask db init && flask db migrate -m "init" && flask db upgrade

echo "[entrypoint] seeding initial data..."
python seed.py || true

echo "[entrypoint] starting: $@"
exec "$@"
