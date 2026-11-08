"""Style pandoc's default reference.docx (fonts, colours, spacing) for the report.

Usage (tools container)::

    pandoc -o docs/relatorio/reference-default.docx --print-default-data-file reference.docx
    python scripts/make_reference_docx.py

Produces ``docs/relatorio/reference.docx`` used by ``make report``.
"""

import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent / "docs" / "relatorio"
NAVY = RGBColor(0x1E, 0x3A, 0x8A)
SLATE = RGBColor(0x33, 0x41, 0x55)


def main() -> int:
    """Apply the visual identity to every style pandoc uses."""
    doc = Document(str(ROOT / "reference-default.docx"))
    for section in doc.sections:
        section.page_height, section.page_width = Cm(29.7), Cm(21.0)
        section.top_margin = section.left_margin = Cm(3)
        section.bottom_margin = section.right_margin = Cm(2)
    styles = doc.styles
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        if name in [s.name for s in styles]:
            style = styles[name]
            style.font.name = "Arial"
            style.font.size = Pt(11)
            style.paragraph_format.space_after = Pt(6)
            style.paragraph_format.line_spacing = 1.3
    if "Body Text" in [s.name for s in styles]:
        styles["Body Text"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    sizes = {1: 16, 2: 13, 3: 12, 4: 11}
    for level, size in sizes.items():
        style = styles[f"Heading {level}"]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = NAVY if level <= 2 else SLATE
        style.paragraph_format.space_before = Pt(18 if level == 1 else 12)
        style.paragraph_format.space_after = Pt(6)
    for name in ("Title", "Subtitle"):
        style = styles[name]
        style.font.name = "Arial"
        style.font.color.rgb = NAVY
    for name in ("Source Code", "Verbatim Char"):
        if name in [s.name for s in styles]:
            styles[name].font.name = "Consolas"
            styles[name].font.size = Pt(8.5)
    for name in ("Caption", "Table Caption", "Image Caption"):
        if name in [s.name for s in styles]:
            style = styles[name]
            style.font.name = "Arial"
            style.font.size = Pt(9.5)
            style.font.italic = False
            style.font.bold = True
            style.font.color.rgb = SLATE
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    capa = styles.add_style("Capa", 1) if "Capa" not in [s.name for s in styles] else styles["Capa"]
    capa.base_style = styles["Normal"]
    capa.font.name = "Arial"
    capa.font.size = Pt(13)
    capa.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    capa.paragraph_format.space_after = Pt(10)
    titulo = styles.add_style("Capa Titulo", 1) if "Capa Titulo" not in [s.name for s in styles] else styles["Capa Titulo"]
    titulo.base_style = capa
    titulo.font.size = Pt(18)
    titulo.font.bold = True
    titulo.font.color.rgb = NAVY
    doc.save(str(ROOT / "reference.docx"))
    print(ROOT / "reference.docx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
