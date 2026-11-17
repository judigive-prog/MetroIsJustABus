# Multi-stage Dockerfile for ticketing-service (conventions.md: Containers)
FROM python:3.13-slim-bookworm AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

# metro-common is an editable path dependency (see uv.lock), so it must live at the
# same path in the builder and in the runner image.
COPY packages/metro_common/ /app/packages/metro_common/
COPY apps/ticketing-service/pyproject.toml apps/ticketing-service/uv.lock /app/apps/ticketing-service/

WORKDIR /app/apps/ticketing-service
RUN uv sync --locked --no-dev

# Final runtime image
FROM python:3.13-slim-bookworm AS runner

# Non-root user for security (conventions.md: Containers)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

WORKDIR /app/apps/ticketing-service

COPY --chown=appuser:appgroup apps/ticketing-service/ /app/apps/ticketing-service/
COPY --from=builder /app/packages/metro_common/ /app/packages/metro_common/
COPY --from=builder /app/apps/ticketing-service/.venv /app/apps/ticketing-service/.venv

USER appuser

EXPOSE 8000

ENV PATH="/app/apps/ticketing-service/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]