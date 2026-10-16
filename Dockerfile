FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
RUN pip install --no-cache-dir uv \
    && uv sync --locked --no-dev --no-editable \
    && groupadd --system inventory \
    && useradd --system --gid inventory --home-dir /app inventory

COPY alembic.ini ./
COPY alembic ./alembic
RUN chown -R inventory:inventory /app

USER inventory
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
