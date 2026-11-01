# One image for every pipeline step (ingest, dbt run, dbt test, export).
# Same code as the laptop and GitHub Actions runs, so all three behave the same.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PULSE_DATA_DIR=/data \
    PULSE_WAREHOUSE=/data/warehouse/pulse.duckdb \
    DBT_SEND_ANONYMOUS_USAGE_STATS=false

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingest/ ingest/
COPY models/ models/
COPY seeds/ seeds/
COPY dashboard/export_marts.py dashboard/export_marts.py

# dbt parses the project once at build time, so a broken model fails the build, not the run.
RUN cd models && dbt parse --profiles-dir . >/dev/null

# No API keys in the image: they arrive at run time as env vars from a Kubernetes secret.
