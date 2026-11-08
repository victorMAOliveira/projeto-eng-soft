# ADR-006 — Ferramentas em containers e host enxuto

**Status:** Aceito · **Sprint:** 0

## Contexto

O host da avaliação tem apenas Docker (Compose v2), Git, Make e Python. Os
membros da equipe usam sistemas operacionais diferentes (inclusive Windows).

## Decisão

- Toda ferramenta roda em container: a imagem `tools` (lint, testes, seed, e2e,
  avaliação), `minlag/mermaid-cli` (diagramas), `pandoc/core` (DOCX/HTML) e
  `mcr.microsoft.com/playwright/python` (prints e PDF).
- O `Makefile` só chama `docker`/`docker compose`, para funcionar com GNU Make
  tanto em `sh` quanto em `cmd.exe`.
- Segredos ficam no `.env` (ignorado pelo Git); `make env` gera valores
  aleatórios a partir do `.env.example`.

## Consequências

- (+) Reprodutibilidade: as mesmas versões rodam no CI e nas máquinas da equipe.
- (−) Primeira execução mais lenta (download de imagens).
