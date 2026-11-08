# syntax=docker/dockerfile:1.7
# Tooling image: lint, tests, seed, e2e, offline evaluation and report helpers.
# The repository is bind-mounted at /work at runtime (see docker-compose `tools`).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/work/components/eh_auth/src:/work/components/eh_events/src:/work/components/eh_db/src:/work/components/eh_observability/src:/work/components/eh_http/src:/work/components/eh_ui/src
COPY scripts/requirements-dev.txt /tmp/requirements-dev.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r /tmp/requirements-dev.txt
WORKDIR /work
CMD ["python", "scripts/run_tests.py"]
