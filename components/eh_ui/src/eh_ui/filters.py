"""pt-BR formatting helpers exposed as Jinja filters."""

from datetime import date, datetime

from jinja2 import Environment

from eh_ui.services import service_color, service_label

STATUS_LABELS = {
    "submitted": "Enviada",
    "under_review": "Em análise",
    "approved": "Aprovada",
    "rejected": "Rejeitada",
    "withdrawn": "Retirada",
    "agreement_pending": "TCE pendente",
    "active": "Estágio ativo",
    "completed": "Concluído",
    "terminated": "Rescindido",
    "open": "Aberta",
    "closed": "Encerrada",
    "pending_approval": "Aguardando coordenação",
    "reviewed": "Revisado",
    "up": "Operacional",
    "degraded": "Degradado",
    "down": "Fora do ar",
}

MODALITY_LABELS = {"onsite": "Presencial", "remote": "Remoto", "hybrid": "Híbrido"}


def status_label(status: str | None) -> str:
    """Translate a status code into Portuguese."""
    return STATUS_LABELS.get(status or "", status or "—")


def modality_label(modality: str | None) -> str:
    """Translate a modality code into Portuguese."""
    return MODALITY_LABELS.get(modality or "", modality or "—")


def brl(value: float | int | None) -> str:
    """Format ``value`` as Brazilian currency, e.g. ``R$ 1.234,50``."""
    if value is None:
        return "—"
    text = f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {text}"


def _parse(value: str | date | datetime | None) -> date | datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def date_br(value: str | date | datetime | None) -> str:
    """Format a date (or ISO string) as ``dd/mm/aaaa``."""
    parsed = _parse(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


def datetime_br(value: str | datetime | None) -> str:
    """Format a datetime (or ISO string) as ``dd/mm/aaaa hh:mm``."""
    parsed = _parse(value)
    if parsed is None:
        return "—"
    if not isinstance(parsed, datetime):
        return parsed.strftime("%d/%m/%Y")
    return parsed.strftime("%d/%m/%Y %H:%M")


def pct(value: float | None, digits: int = 0) -> str:
    """Format a 0..1 score as a percentage string."""
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def register_filters(env: Environment) -> Environment:
    """Install every eh_ui filter (and the ``SERVICES`` global) into ``env``."""
    from eh_ui.services import SERVICES

    env.filters.update(
        status_label=status_label,
        modality_label=modality_label,
        brl=brl,
        date_br=date_br,
        datetime_br=datetime_br,
        pct=pct,
        service_color=service_color,
        service_label=service_label,
    )
    env.globals["EH_SERVICES"] = SERVICES
    return env
