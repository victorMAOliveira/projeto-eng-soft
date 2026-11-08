# syntax=docker/dockerfile:1.7
# Build context: repository root (components are installed from local paths).

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY components/eh_http components/eh_http
COPY components/eh_observability components/eh_observability
COPY components/eh_ui components/eh_ui
COPY frontend/web/requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements.txt \
        ./components/eh_http ./components/eh_observability ./components/eh_ui

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels
WORKDIR /app
COPY frontend/web/web_frontend ./web_frontend
USER app
EXPOSE 8080
CMD ["uvicorn", "web_frontend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
