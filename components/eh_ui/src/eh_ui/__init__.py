"""eh_ui — reusable presentation layer for EstágioHub web interfaces.

Public interface:

* :func:`templates_dir` — directory to add to a Jinja loader; macros live in
  ``eh_ui/macros.html`` (``card``, ``table``, ``service_badge``, ``alert``,
  ``status_pill``, ``score_bar``, ``service_card``, ``stat``, ``empty_state``).
* :func:`static_dir` — directory with ``eh_ui.css``.
* :func:`register_filters` — installs the pt-BR filters below in an environment.
* :data:`SERVICES` / :func:`service_color` / :func:`service_label` — identity of
  each microservice (label and colour used by badges and the highlight toggle).
* :func:`status_label`, :func:`modality_label`, :func:`brl`, :func:`date_br`,
  :func:`datetime_br`, :func:`pct` — formatting helpers.
"""

from eh_ui.filters import (
    brl,
    date_br,
    datetime_br,
    modality_label,
    pct,
    register_filters,
    status_label,
)
from eh_ui.paths import static_dir, templates_dir
from eh_ui.services import SERVICES, ServiceMeta, service_color, service_label

__version__ = "0.1.0"

__all__ = [
    "SERVICES",
    "ServiceMeta",
    "brl",
    "date_br",
    "datetime_br",
    "modality_label",
    "pct",
    "register_filters",
    "service_color",
    "service_label",
    "static_dir",
    "status_label",
    "templates_dir",
]
