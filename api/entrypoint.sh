#!/bin/sh
set -e

echo "Waiting for DB..."
python - <<'PY'
import os, time
import psycopg

dsn = os.getenv("DATABASE_DSN") or os.getenv("DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
if not dsn:
    raise RuntimeError("DATABASE_DSN or DATABASE_URL not set")

for i in range(60):
    try:
        with psycopg.connect(dsn) as conn:
            print("DB is ready")
            break
    except Exception as e:
        print(f"DB not ready yet ({i+1}/60): {e}")
        time.sleep(1)
else:
    raise RuntimeError("DB did not become ready in time")
PY

echo "Running DB migrations..."
python -m api.scripts.migrate

echo "Starting API..."
exec gunicorn -k uvicorn.workers.UvicornWorker api.main:app \
  --bind 0.0.0.0:8000 \
  --workers 2