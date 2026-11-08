"""Termo de Compromisso de Estágio (TCE) rendering with ReportLab + PNG preview."""

import io
from dataclasses import dataclass
from datetime import date, datetime

import pypdfium2
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INSTITUTION = "Universidade Federal de Alagoas (UFAL)"


class MissingInsuranceError(ValueError):
    """Art. 9, IV of Lei 11.788/2008: no TCE without personal accident insurance."""


@dataclass(frozen=True, slots=True)
class AgreementData:
    """Everything printed on the TCE."""

    agreement_id: str
    version: int
    student_name: str
    student_course: str | None
    company_name: str
    internship_title: str
    start_date: date
    end_date: date
    hours_per_day: int
    hours_per_week: int
    stipend: float
    insurer: str | None
    insurance_policy: str | None
    supervisor_name: str
    activities: str
    is_pcd: bool
    generated_at: datetime


def _brl(value: float) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def render_agreement_pdf(data: AgreementData) -> bytes:
    """Render the TCE as an A4 PDF.

    Raises:
        MissingInsuranceError: insurer or policy number missing (the TCE is not issued).
    """
    if not (data.insurer or "").strip() or not (data.insurance_policy or "").strip():
        raise MissingInsuranceError("TCE requer seguro contra acidentes pessoais")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.2 * cm,
        rightMargin=2.2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Termo de Compromisso de Estágio",
        author="EstágioHub",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=15, spaceAfter=2)
    subtitle = ParagraphStyle(
        "s",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        textColor=colors.HexColor("#475569"),
    )
    body = ParagraphStyle(
        "b", parent=styles["Normal"], fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=5
    )
    heading = ParagraphStyle(
        "h",
        parent=styles["Heading4"],
        fontSize=10,
        spaceBefore=6,
        spaceAfter=3,
        textColor=colors.HexColor("#1e3a8a"),
    )
    small = ParagraphStyle(
        "sm", parent=body, fontSize=7.5, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER
    )

    period = f"{data.start_date:%d/%m/%Y} a {data.end_date:%d/%m/%Y}"
    parties = Table(
        [
            ["INSTITUIÇÃO DE ENSINO", INSTITUTION],
            ["CONCEDENTE", data.company_name],
            [
                "ESTAGIÁRIO(A)",
                f"{data.student_name} — {data.student_course or 'curso não informado'}",
            ],
            ["ESTÁGIO", data.internship_title],
        ],
        colWidths=[4.2 * cm, 12.3 * cm],
    )
    parties.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 8),
                ("FONT", (1, 0), (1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#334155")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eff6ff")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    duration_clause = (
        "Por se tratar de estagiário(a) com deficiência, não se aplica o limite de 2 (dois) anos "
        "na mesma concedente (art. 11)."
        if data.is_pcd
        else "A duração do estágio na mesma concedente não excederá 2 (dois) anos (art. 11)."
    )
    clauses = [
        (
            "CLÁUSULA 1ª — Objeto",
            "Este termo formaliza a realização de estágio, ato educativo escolar supervisionado, "
            "nos termos da Lei nº 11.788/2008, sem vínculo empregatício de qualquer "
            "natureza (art. 3º).",
        ),
        ("CLÁUSULA 2ª — Vigência", f"O estágio terá vigência de {period}. {duration_clause}"),
        (
            "CLÁUSULA 3ª — Jornada",
            f"A jornada será de {data.hours_per_day} horas diárias e {data.hours_per_week} horas "
            "semanais, compatível com as atividades acadêmicas e dentro do limite de "
            "6 horas diárias "
            "e 30 horas semanais (art. 10, II).",
        ),
        (
            "CLÁUSULA 4ª — Bolsa",
            f"O(a) estagiário(a) receberá bolsa mensal de {_brl(data.stipend)} (art. 12).",
        ),
        (
            "CLÁUSULA 5ª — Seguro",
            f"A concedente contratou seguro contra acidentes pessoais em favor do(a) estagiário(a) "
            f"junto à seguradora {data.insurer}, apólice nº {data.insurance_policy} (art. 9º, IV).",
        ),
        (
            "CLÁUSULA 6ª — Supervisão e orientação",
            f"As atividades serão supervisionadas por {data.supervisor_name}, indicado(a) pela "
            "concedente (art. 9º, III), e acompanhadas pela coordenação de estágio da instituição "
            "de ensino (art. 7º, III).",
        ),
        (
            "CLÁUSULA 7ª — Relatórios",
            "O(a) estagiário(a) apresentará relatório de atividades em periodicidade não superior "
            "a 6 (seis) meses (art. 7º, IV e art. 9º, VII).",
        ),
        ("CLÁUSULA 8ª — Atividades", data.activities or "Conforme plano de atividades anexo."),
        (
            "CLÁUSULA 9ª — Recesso",
            "É assegurado recesso de 30 (trinta) dias a cada ano de estágio, ou proporcional, "
            "preferencialmente durante as férias escolares (art. 13).",
        ),
    ]

    story = [
        Paragraph("TERMO DE COMPROMISSO DE ESTÁGIO", title),
        Paragraph("Lei nº 11.788, de 25 de setembro de 2008", subtitle),
        Spacer(1, 10),
        parties,
        Spacer(1, 8),
    ]
    for heading_text, text in clauses:
        story += [Paragraph(heading_text, heading), Paragraph(text, body)]

    signatures = Table(
        [["", "", ""], ["Estagiário(a)", "Concedente", "Instituição de Ensino"]],
        colWidths=[5.3 * cm] * 3,
        rowHeights=[1.4 * cm, 0.6 * cm],
    )
    signatures.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 1), (0, 1), 0.6, colors.black),
                ("LINEABOVE", (1, 1), (1, 1), 0.6, colors.black),
                ("LINEABOVE", (2, 1), (2, 1), 0.6, colors.black),
                ("FONT", (0, 1), (-1, 1), "Helvetica", 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story += [
        Spacer(1, 14),
        signatures,
        Spacer(1, 10),
        Paragraph(
            f"Documento gerado automaticamente pelo EstágioHub em "
            f"{data.generated_at:%d/%m/%Y %H:%M} (UTC) · TCE {data.agreement_id} · versão "
            f"{data.version}. Documento de demonstração acadêmica, sem validade jurídica.",
            small,
        ),
    ]
    doc.build(story)
    return buffer.getvalue()


def render_preview_png(pdf_bytes: bytes, scale: float = 1.4) -> bytes:
    """Rasterise the first page of a PDF to PNG (used by the TCE preview screen)."""
    document = pypdfium2.PdfDocument(pdf_bytes)
    try:
        image = document[0].render(scale=scale).to_pil()
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()
    finally:
        document.close()
