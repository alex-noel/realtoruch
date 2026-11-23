FROM python:3.12.16-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml backend/setup.py ./
COPY backend/requirements-runtime.lock ./
COPY backend/realtoruch ./realtoruch
RUN pip install --no-cache-dir -r requirements-runtime.lock . && pip check
COPY infra/sql /app/infra/sql
ENV REALTORUCH_SQL_DIR=/app/infra/sql
COPY config /config
ENV CONNECTORS_CONFIG=/config/sources.json
RUN useradd --uid 10001 --create-home app
RUN mkdir -p /var/lib/realtoruch/media && chown app:app /var/lib/realtoruch/media && chmod 700 /var/lib/realtoruch/media
USER app
EXPOSE 8000
CMD ["python", "-m", "realtoruch.runtime", "uvicorn", "realtoruch.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM base AS cloud
USER root
COPY backend/requirements-cloud.lock ./
RUN pip install --no-cache-dir -r requirements-cloud.lock '.[cloud]' && pip check
USER app

FROM base AS dataflow
USER root
COPY backend/requirements-gcp.lock ./
RUN pip install --no-cache-dir -r requirements-gcp.lock '.[gcp]' && pip check
COPY --from=gcr.io/dataflow-templates-base/python312-template-launcher-base:20261118-rc00@sha256:977e1f77d4e96df51e4fcfcb3d4436bfa7325a1afc5e9d29ecb6ca97f1c2ae3e \
    /opt/google/dataflow/python_template_launcher /opt/google/dataflow/python_template_launcher
COPY infra/dataflow/launch.py /app/launch.py
COPY infra/dataflow/requirements.txt /app/dataflow-requirements.txt
ENV FLEX_TEMPLATE_PYTHON_PY_FILE=/app/launch.py
ENV BEAM_SETUP_FILE=/app/setup.py BEAM_REQUIREMENTS_FILE=/app/dataflow-requirements.txt
ENTRYPOINT ["/opt/google/dataflow/python_template_launcher"]
