FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY manage.py ./
COPY config/ ./config/
COPY workflows/ ./workflows/
RUN SECRET_KEY=build-collectstatic-key \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    .venv/bin/python manage.py collectstatic --noinput

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/manage.py ./
COPY --from=builder /app/config ./config
COPY --from=builder /app/workflows ./workflows
COPY --from=builder /app/staticfiles ./staticfiles
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production
EXPOSE 8080
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8080"]
