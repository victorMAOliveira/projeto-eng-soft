"""Which notifications each event produces (pure function, easy to test).

Recipients are inbox keys: ``user:<id>`` for a person or ``role:coordinator``
for every member of the internship coordination.
"""

from dataclasses import dataclass

from eh_events import Event, EventType, typed_payload

STATUS_TEXT = {
    "under_review": "está em análise pela empresa",
    "approved": "foi aprovada! O Termo de Compromisso será gerado",
    "rejected": "não foi aprovada desta vez",
    "withdrawn": "foi retirada",
    "agreement_pending": "aguarda a aprovação do TCE pela coordenação",
    "active": "virou estágio ativo",
    "completed": "foi concluída — estágio encerrado",
    "terminated": "foi rescindida",
}


@dataclass(frozen=True, slots=True)
class Notice:
    """One notification to deliver to ``recipient``."""

    recipient: str
    title: str
    message: str
    kind: str = "info"  # info | success | warning
    link: str | None = None


def user(user_id: int) -> str:
    """Inbox key of a person."""
    return f"user:{user_id}"


COORDINATION = "role:coordinator"


def notices_for(event: Event) -> list[Notice]:
    """Translate a domain event into the notifications of the actors involved."""
    p = typed_payload(event)
    match event.event_type:
        case EventType.USER_REGISTERED:
            return [
                Notice(
                    user(p.user_id),
                    "Bem-vindo(a) ao EstágioHub!",
                    "Sua conta foi criada. Complete seu perfil para receber recomendações.",
                    "success",
                    "/perfil",
                )
            ]
        case EventType.PROFILE_UPDATED:
            return [
                Notice(
                    user(p.user_id),
                    "Perfil atualizado",
                    "Suas recomendações de vagas foram recalculadas.",
                    "info",
                    "/recomendacoes",
                )
            ]
        case EventType.INTERNSHIP_PUBLISHED:
            return [
                Notice(
                    user(p.company_id),
                    "Vaga publicada",
                    f"A vaga “{p.title}” está aberta para candidaturas.",
                    "success",
                    f"/vagas/{p.internship_id}",
                )
            ]
        case EventType.INTERNSHIP_CLOSED:
            return [
                Notice(
                    user(p.company_id),
                    "Vaga encerrada",
                    "A vaga não recebe mais candidaturas.",
                    "info",
                    f"/vagas/{p.internship_id}",
                )
            ]
        case EventType.APPLICATION_SUBMITTED:
            return [
                Notice(
                    user(p.student_id),
                    "Candidatura enviada",
                    f"Sua candidatura para “{p.internship_title}” foi registrada.",
                    "success",
                    "/candidaturas",
                ),
                Notice(
                    user(p.company_id),
                    "Nova candidatura",
                    f"{p.student_name} se candidatou a “{p.internship_title}”.",
                    "info",
                    f"/vagas/{p.internship_id}/candidatos",
                ),
            ]
        case EventType.APPLICATION_STATUS_CHANGED:
            kind = {
                "approved": "success",
                "active": "success",
                "rejected": "warning",
                "terminated": "warning",
            }.get(p.to_status, "info")
            notices = [
                Notice(
                    user(p.student_id),
                    "Atualização da candidatura",
                    f"Sua candidatura para “{p.internship_title}” "
                    f"{STATUS_TEXT.get(p.to_status, p.to_status)}.",
                    kind,
                    f"/candidaturas/{p.application_id}",
                )
            ]
            if p.to_status in ("withdrawn", "active", "completed", "terminated"):
                notices.append(
                    Notice(
                        user(p.company_id),
                        "Atualização de candidato",
                        f"{p.student_name} — “{p.internship_title}”: "
                        f"{STATUS_TEXT.get(p.to_status, p.to_status)}.",
                        kind,
                        f"/candidaturas/{p.application_id}",
                    )
                )
            return notices
        case EventType.AGREEMENT_GENERATED:
            link = f"/termos/{p.agreement_id}"
            return [
                Notice(
                    user(p.student_id),
                    "TCE gerado",
                    "Seu Termo de Compromisso foi gerado e aguarda a coordenação.",
                    "info",
                    link,
                ),
                Notice(
                    user(p.company_id),
                    "TCE gerado",
                    f"Termo de {p.student_name or 'estagiário(a)'} gerado; aguardando coordenação.",
                    "info",
                    link,
                ),
                Notice(
                    COORDINATION,
                    "TCE aguardando aprovação",
                    f"{p.student_name or 'Estagiário(a)'} — {p.internship_title or 'estágio'} "
                    f"({p.company_name or 'concedente'}).",
                    "warning",
                    link,
                ),
            ]
        case EventType.AGREEMENT_APPROVED:
            link = f"/termos/{p.agreement_id}"
            return [
                Notice(
                    user(p.student_id),
                    "TCE aprovado — estágio ativo!",
                    "A coordenação aprovou seu Termo de Compromisso.",
                    "success",
                    link,
                ),
                Notice(
                    user(p.company_id),
                    "TCE aprovado",
                    f"O estágio de {p.student_name or 'estagiário(a)'} está ativo.",
                    "success",
                    link,
                ),
            ]
        case EventType.REPORT_SUBMITTED:
            return [
                Notice(
                    COORDINATION,
                    "Relatório de atividades enviado",
                    f"{p.student_name or 'Estagiário(a)'} enviou “{p.title or 'relatório'}” "
                    f"(versão {p.version}).",
                    "info",
                    "/relatorios",
                ),
                Notice(
                    user(p.company_id),
                    "Relatório enviado",
                    f"{p.student_name or 'Estagiário(a)'} enviou um relatório de atividades.",
                    "info",
                    "/relatorios",
                ),
            ]
        case EventType.REPORT_DUE_SOON:
            text = (
                f"vencido há {-p.days_left} dia(s)"
                if p.overdue
                else f"vence em {p.days_left} dia(s) ({p.due_date:%d/%m/%Y})"
            )
            return [
                Notice(
                    user(p.student_id),
                    "Prazo do relatório de atividades",
                    f"Seu relatório semestral está {text}.",
                    "warning",
                    "/relatorios",
                ),
                Notice(
                    COORDINATION,
                    "Relatório a vencer",
                    f"{p.student_name or 'Estagiário(a)'}: relatório {text}.",
                    "warning",
                    "/relatorios",
                ),
            ]
    return []  # pragma: no cover - every EventType is handled above
