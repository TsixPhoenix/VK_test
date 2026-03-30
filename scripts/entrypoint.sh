#!/usr/bin/env sh
set -eu

echo "Waiting for database..."
python - <<'PY'
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def wait_for_db() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for container startup.")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    max_attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "30"))
    sleep_seconds = float(os.getenv("DB_WAIT_SLEEP_SECONDS", "1"))

    try:
        for _ in range(max_attempts):
            try:
                async with engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
                return
            except Exception:
                await asyncio.sleep(sleep_seconds)
    finally:
        await engine.dispose()

    raise RuntimeError("Database is unavailable after retries.")


try:
    asyncio.run(wait_for_db())
except Exception as exc:  # noqa: BLE001
    print(f"DB wait failed: {exc}", file=sys.stderr)
    raise
PY

echo "Applying database migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
