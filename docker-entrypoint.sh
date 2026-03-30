#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse

database_url = os.environ.get("DATABASE_URL", "").strip()
if not database_url:
    raise SystemExit(0)

parsed = urlparse(database_url)
if parsed.scheme not in {"postgres", "postgresql"}:
    raise SystemExit(0)

host = parsed.hostname or "db"
port = parsed.port or 5432
deadline = time.time() + 60

while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        if time.time() >= deadline:
            raise SystemExit(f"Timed out waiting for database at {host}:{port}")
        time.sleep(1)
PY

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

if [ "${RUN_COLLECTSTATIC:-0}" = "1" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
