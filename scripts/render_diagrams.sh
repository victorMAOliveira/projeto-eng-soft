#!/bin/sh
# Render every docs/architecture/*.mmd to docs/relatorio/img/diagrams/*.png
# (runs inside the minlag/mermaid-cli image: `make report`).
set -eu
MMDC="$(command -v mmdc || echo /home/mermaidcli/node_modules/.bin/mmdc)"
OUT=/work/docs/relatorio/img/diagrams
mkdir -p "$OUT"
for source in /work/docs/architecture/*.mmd; do
  name="$(basename "$source" .mmd)"
  echo "mermaid: $name"
  "$MMDC" -q -i "$source" -o "$OUT/$name.png" -b white -w 1600 -s 2 -p /puppeteer-config.json
done
