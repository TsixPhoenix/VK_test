FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.lock ./
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.lock \
    && pip install --prefix=/install --no-deps .

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app appuser

COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts/entrypoint.sh ./scripts/entrypoint.sh

RUN sed -i 's/\r$//' ./scripts/entrypoint.sh \
    && chmod +x ./scripts/entrypoint.sh \
    && chown -R appuser:app /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["./scripts/entrypoint.sh"]
