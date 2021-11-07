FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml backend/setup.py ./
COPY backend/requirements-runtime.lock ./
COPY backend/realtoruch ./realtoruch
RUN pip install --no-cache-dir -r requirements-runtime.lock .
COPY config /config
ENV CONNECTORS_CONFIG=/config/sources.json
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["python", "-m", "realtoruch.runtime", "uvicorn", "realtoruch.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM base AS cloud
USER root
RUN pip install --no-cache-dir -c requirements-runtime.lock '.[cloud]'
USER app

FROM base AS dataflow
USER root
RUN pip install --no-cache-dir -c requirements-runtime.lock '.[gcp]'
COPY --from=gcr.io/dataflow-templates-base/python312-template-launcher-base:latest /opt/google/dataflow/python_template_launcher /opt/google/dataflow/python_template_launcher
COPY infra/dataflow/launch.py /app/launch.py
COPY infra/dataflow/requirements.txt /app/dataflow-requirements.txt
ENV FLEX_TEMPLATE_PYTHON_PY_FILE=/app/launch.py
ENV BEAM_SETUP_FILE=/app/setup.py BEAM_REQUIREMENTS_FILE=/app/dataflow-requirements.txt
ENTRYPOINT ["/opt/google/dataflow/python_template_launcher"]
