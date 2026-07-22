# syntax=docker/dockerfile:1
FROM python:3.11-slim

ARG VCS_REF=unknown
ARG VERSION=edge

LABEL org.opencontainers.image.title="Healthcare Lab" \
      org.opencontainers.image.description="Healthcare interoperability lab application" \
      org.opencontainers.image.source="https://github.com/Tzu-Huang/healthcare-lab" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LAB_APP_HOST=0.0.0.0 \
    LAB_APP_PORT=5000

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY backend ./backend
COPY frontend ./frontend

RUN mkdir -p /app/instance /data/gdt-bridge

EXPOSE 5000 6665
VOLUME ["/app/instance", "/data/gdt-bridge"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)" || exit 1

# One worker preserves the application's single-process OIE listener ownership.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "backend.app_factory:app"]
