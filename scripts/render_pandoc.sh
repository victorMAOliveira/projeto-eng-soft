#!/bin/sh
# Render docs/relatorio/relatorio.md to DOCX (styled reference-doc) and to a
# self-contained HTML that `build_report.py pdf` prints to PDF.
# Runs inside the pandoc/core image (`make report`).
set -eu
cd /work/docs/relatorio
mkdir -p build
pandoc relatorio.md --from markdown+pipe_tables+fenced_divs+raw_attribute+implicit_figures \
  --to docx --reference-doc=reference.docx --resource-path=. \
  --metadata lang=pt-BR -o build/relatorio.docx
echo "pandoc: build/relatorio.docx"
pandoc relatorio.md --from markdown+pipe_tables+fenced_divs+raw_attribute+implicit_figures \
  --to html5 --standalone --embed-resources --toc --toc-depth=2 --css=style.css \
  --resource-path=. --metadata lang=pt-BR \
  --variable pagetitle="EstágioHub — Relatório Final" -o build/relatorio.html
echo "pandoc: build/relatorio.html"
