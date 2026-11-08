# Playwright image (browsers + system deps) plus the matching Python package,
# which the official image does not ship. Used by `make screenshots` and the
# HTML -> PDF step of `make report`.
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble
RUN pip install --no-cache-dir --break-system-packages playwright==1.49.1
WORKDIR /work
