# Multi-stage Dockerfile for notification-service (conventions.md: Containers)
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY packages/metro_common/ /build/packages/metro_common/
COPY apps/notification-service/pyproject.toml /build/apps/notification-service/

WORKDIR /build/apps/notification-service
RUN uv pip install --system --no-cache -r pyproject.toml

# Final runtime image
FROM python:3.13-slim-bookworm AS runner

WORKDIR /app

# Non-root user for security (conventions.md: Containers)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=appuser:appgroup packages/metro_common/ /app/packages/metro_common/
COPY --chown=appuser:appgroup apps/notification-service/ /app/

USER appuser

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
