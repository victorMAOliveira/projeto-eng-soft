# ADR-007 — Frontend renderizado no servidor com Jinja2 + HTMX

**Status:** Aceito · **Sprint:** 1

## Contexto

O frontend precisa: consumir apenas o API Gateway, funcionar sem internet na
apresentação (sem CDN), mostrar em cada painel qual microsserviço forneceu os
dados e ser construído rapidamente por uma equipe pequena que já usa Python.

## Decisão

- `web-frontend` em FastAPI + Jinja2, com HTMX 2.0.4 empacotado localmente
  (`static/vendor/htmx.min.js`, obtido do registro npm e versionado) para
  atualizações parciais (busca de vagas, auto-refresh do status).
- O JWT fica em *cookie* `HttpOnly` + `SameSite=Lax`; o frontend só lê as
  *claims* para montar o menu — quem valida o token é o gateway.
- Cada chamada ao gateway devolve `ApiResult(status, data, served_by)`; o
  `served_by` vem do header `X-Served-By` e alimenta o *badge* do painel
  (macros do componente `eh_ui`).
- Painéis do dashboard são buscados em paralelo e de forma independente:
  um 503 apaga só o próprio painel (degradação graciosa).

## Consequências

- (+) Nenhum *build* de JavaScript; o mesmo Python em todo o sistema.
- (+) O token nunca fica acessível a JavaScript (mitiga XSS).
- (−) Interatividade limitada a trocas de fragmentos HTML; suficiente para o
  escopo.
