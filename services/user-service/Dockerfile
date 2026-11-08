# syntax=docker/dockerfile:1.7
# Build context: repository root (components are installed from local paths).

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY components/eh_auth components/eh_auth
COPY components/eh_db components/eh_db
COPY components/eh_events components/eh_events
COPY components/eh_observability components/eh_observability
COPY services/user-service/requirements.txt requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels -r requirements.txt \
        ./components/eh_auth ./components/eh_db ./components/eh_events ./components/eh_observability

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd --create-home --uid 10001 app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/*.whl && rm -rf /wheels
WORKDIR /app
COPY services/user-service/alembic.ini ./
COPY services/user-service/alembic ./alembic
COPY services/user-service/user_service ./user_service
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn user_service.main:create_app --factory --host 0.0.0.0 --port 8000 --no-access-log"]
