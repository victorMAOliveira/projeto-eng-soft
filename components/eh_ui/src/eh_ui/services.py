"""Visual identity of each EstágioHub microservice."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceMeta:
    """Label, colour and short description shown for a microservice."""

    name: str
    label: str
    color: str
    description: str
    database: str


SERVICES: dict[str, ServiceMeta] = {
    meta.name: meta
    for meta in (
        ServiceMeta(
            "api-gateway", "API Gateway", "#475569", "Entrada única, JWT e roteamento", "—"
        ),
        ServiceMeta(
            "user-service", "Usuários", "#2563eb", "Contas, papéis, JWT e perfis", "PostgreSQL"
        ),
        ServiceMeta(
            "internship-service", "Vagas", "#059669", "Publicação e busca de vagas", "PostgreSQL"
        ),
        ServiceMeta(
            "application-service",
            "Candidaturas",
            "#d97706",
            "Candidaturas, estágio e regras legais",
            "PostgreSQL",
        ),
        ServiceMeta(
            "document-service",
            "Documentos",
            "#7c3aed",
            "TCE em PDF e relatórios",
            "MongoDB + volume",
        ),
        ServiceMeta(
            "notification-service", "Notificações", "#db2777", "Caixa de notificações", "Redis"
        ),
        ServiceMeta(
            "recommendation-service",
            "Recomendação",
            "#0891b2",
            "Recomendação híbrida explicável",
            "PostgreSQL",
        ),
        ServiceMeta(
            "agent-service", "Agentes IA", "#dc2626", "Assistentes e acompanhamento", "PostgreSQL"
        ),
        ServiceMeta("web-frontend", "Frontend", "#64748b", "Interface web (Jinja + HTMX)", "—"),
    )
}

_FALLBACK_COLOR = "#94a3b8"


def service_color(name: str | None) -> str:
    """Hex colour of service ``name`` (grey for unknown services)."""
    meta = SERVICES.get(name or "")
    return meta.color if meta else _FALLBACK_COLOR


def service_label(name: str | None) -> str:
    """Human label of service ``name`` (the name itself when unknown)."""
    meta = SERVICES.get(name or "")
    return meta.label if meta else (name or "")
