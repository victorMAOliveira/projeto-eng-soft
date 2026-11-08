"""EstágioHub web frontend — server-rendered UI (FastAPI + Jinja2 + HTMX).

The frontend talks **only** to the API Gateway; every panel shows which
microservice provided its data (``X-Served-By`` relayed by the gateway).
"""

__version__ = "0.1.0"
SERVICE_NAME = "web-frontend"
