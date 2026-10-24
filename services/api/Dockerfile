FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
COPY services/api/pyproject.toml services/api/
COPY services/api/bionexus services/api/bionexus
COPY skills skills
RUN pip install --no-cache-dir ./services/api uvicorn \
    && useradd --system --uid 10001 app
USER app
ENV PYTHONUNBUFFERED=1 BIONEXUS_SKILLS_DIR=/app/skills
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u;u.urlopen('http://localhost:8000/healthz')"
CMD ["uvicorn", "bionexus.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
