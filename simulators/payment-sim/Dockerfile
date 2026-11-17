# Multi-stage Dockerfile for payment-sim (conventions.md: Containers)
FROM python:3.13-slim-bookworm AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY simulators/payment-sim/pyproject.toml simulators/payment-sim/uv.lock /app/simulators/payment-sim/

WORKDIR /app/simulators/payment-sim
RUN uv sync --locked --no-dev

# Final runtime image
FROM python:3.13-slim-bookworm AS runner

# Non-root user for security (conventions.md: Containers)
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser && \
    mkdir /data && chown appuser:appgroup /data

WORKDIR /app/simulators/payment-sim

COPY --chown=appuser:appgroup simulators/payment-sim/ /app/simulators/payment-sim/
COPY --from=builder /app/simulators/payment-sim/.venv /app/simulators/payment-sim/.venv

USER appuser

EXPOSE 8000

ENV PATH="/app/simulators/payment-sim/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]