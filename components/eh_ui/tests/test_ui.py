from datetime import date, datetime

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from eh_ui import (
    SERVICES,
    brl,
    date_br,
    datetime_br,
    modality_label,
    pct,
    register_filters,
    service_color,
    service_label,
    static_dir,
    status_label,
    templates_dir,
)


@pytest.fixture
def env() -> Environment:
    environment = Environment(loader=FileSystemLoader(templates_dir()), autoescape=True)
    return register_filters(environment)


def render(env: Environment, source: str, **context) -> str:
    template = env.from_string('{% import "eh_ui/macros.html" as ui %}' + source)
    return template.render(**context)


def test_paths_exist():
    assert (templates_dir() / "eh_ui" / "macros.html").is_file()
    assert (static_dir() / "eh_ui.css").is_file()


def test_every_backend_service_has_identity():
    for name in (
        "api-gateway",
        "user-service",
        "internship-service",
        "application-service",
        "document-service",
        "notification-service",
        "recommendation-service",
        "agent-service",
    ):
        assert name in SERVICES
        assert service_color(name).startswith("#")
    assert service_color("unknown") == "#94a3b8"
    assert service_label("user-service") == "Usuários"
    assert service_label("other") == "other"
    assert service_label(None) == ""


def test_filters_format_ptbr():
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(None) == "—"
    assert date_br("2026-11-08") == "08/11/2026"
    assert date_br(date(2026, 1, 2)) == "02/01/2026"
    assert date_br("not a date") == "—"
    assert date_br(None) == "—"
    assert datetime_br("2026-11-08T13:05:00Z") == "08/11/2026 13:05"
    assert datetime_br(datetime(2026, 11, 8, 9, 0)) == "08/11/2026 09:00"
    assert datetime_br(date(2026, 11, 8)) == "08/11/2026"
    assert datetime_br(None) == "—"
    assert status_label("under_review") == "Em análise"
    assert status_label("weird") == "weird"
    assert status_label(None) == "—"
    assert modality_label("remote") == "Remoto"
    assert modality_label(None) == "—"
    assert pct(0.756) == "76%"
    assert pct(0.756, 1) == "75.6%"
    assert pct(None) == "—"


def test_card_with_service_badge_and_body(env):
    html = render(
        env,
        '{% call ui.card("Vagas", service="internship-service", subtitle="abertas") %}'
        "corpo{% endcall %}",
    )
    assert 'data-service="internship-service"' in html
    assert "#059669" in html
    assert "corpo" in html
    assert "abertas" in html
    assert "eh-badge-service" in html


def test_card_without_service_or_caller(env):
    html = render(env, '{{ ui.card("Simples") }}')
    assert "data-service" not in html
    assert "Simples" in html


def test_table_rows_and_empty_state(env):
    html = render(env, "{{ ui.table(['A', 'B'], [[1, 2], [3, 4]]) }}")
    assert html.count("<tr>") == 3
    empty = render(env, "{{ ui.table(['A', 'B'], [], empty='Nada') }}")
    assert 'colspan="2"' in empty and "Nada" in empty


def test_alert_pill_score_stat_service_card_empty(env):
    html = render(
        env,
        "{{ ui.alert('Falhou', kind='error', title='Erro') }}"
        "{{ ui.status_pill('approved') }}"
        "{{ ui.score_bar(0.42, 'Score') }}"
        "{{ ui.stat('Vagas', 30, service='internship-service', hint='abertas') }}"
        "{{ ui.service_card('user-service', status='up') }}"
        "{{ ui.service_card('custom-service') }}"
        "{{ ui.empty_state('Vazio', hint='dica') }}",
    )
    assert 'role="alert"' in html and "Erro" in html
    assert "Aprovada" in html
    assert "width: 42%" in html
    assert "abertas" in html
    assert "eh-dot--up" in html and "Usuários" in html
    assert "custom-service" in html
    assert "dica" in html


def test_score_bar_is_capped(env):
    html = render(env, "{{ ui.score_bar(1.7) }}")
    assert "width: 100%" in html


def test_register_filters_with_strict_undefined():
    environment = Environment(loader=FileSystemLoader(templates_dir()), undefined=StrictUndefined)
    register_filters(environment)
    assert "EH_SERVICES" in environment.globals
    assert environment.filters["brl"](10) == "R$ 10,00"
