# Sprint 0 — Fundação

- **Período:** [PREENCHER: data/hora de início e fim — usar os timestamps do primeiro e do último commit da sprint (`git log sprint-0`)]
- **Duração planejada:** cerca de 2 horas (micro-sprint, formato intensivo)
- **Tag:** `sprint-0`

## Meta da sprint

Ter a fundação técnica pronta: estrutura do repositório, componentes
reutilizáveis instaláveis, API Gateway com JWT e saúde agregada, stack no
Docker Compose com *healthchecks*, CI e as decisões de arquitetura iniciais
registradas.

## Histórias selecionadas

| ID | História | SP |
|---|---|---|
| US-01 | Subir todo o sistema com um comando | 5 |
| US-02 | Componentes reutilizáveis instaláveis | 8 |
| US-03 | API Gateway com JWT e roteamento | 8 |
| US-04 | CI com lint, testes e build | 3 |
| US-05 | Health checks em todos os serviços | 3 |
| | **Total** | **27** |

## Tarefas técnicas

| Tarefa | História | Estimativa |
|---|---|---|
| Estrutura do repositório, `.gitignore`, `.gitattributes`, configuração do `ruff` | US-01 | 0,5 h |
| `eh_observability` (log JSON, *correlation-id*, `/health` `/ready` `/version`) | US-02, US-05 | 1 h |
| `eh_http` (timeout, *retry* com *backoff*, *circuit breaker*) | US-02 | 1 h |
| `eh_auth` (JWT, argon2, `require_role`) | US-02 | 1 h |
| `eh_db` (engine/sessão assíncronas, repositório, Alembic, idempotência) | US-02 | 1 h |
| `eh_events` (contratos, *publisher*, *consumer* com DLQ e idempotência) | US-02 | 1,5 h |
| `eh_ui` (esqueleto: macros, filtros, CSS) | US-02 | 0,5 h |
| `api-gateway` (rotas, políticas de papel, proxy, `GET /services`) + testes | US-03, US-05 | 1,5 h |
| `docker-compose.yml`, Dockerfile multi-stage, `Makefile`, `make env` | US-01 | 1 h |
| Imagem `tools` e `scripts/run_tests.py` | US-01, US-04 | 0,5 h |
| GitHub Actions (lint, testes, build) | US-04 | 0,5 h |
| ADRs 001–006 e Product Backlog | — | 0,5 h |

## Definition of Done

Aplicada a DoD global do projeto:

- [x] Código com *docstrings* (regras `D100`, `D101`, `D103` do `ruff`).
- [x] Testes passando (`make test`).
- [x] `ruff` sem erros (`ruff check` e `ruff format --check`).
- [x] Serviço *healthy* no Compose (`api-gateway` e `rabbitmq`).
- [x] Documentação atualizada (READMEs dos componentes, ADRs, PROGRESS.md).

## Review — o que foi entregue

| Entrega | Evidência |
|---|---|
| Estrutura e lint | commit `cf75b69` |
| `eh_observability` e `eh_http` | commit `ab7e49c` |
| `eh_auth`, `eh_db` e `eh_events` | commit `74f736d` |
| `eh_ui` (esqueleto) | commit `3eb62d0` |
| API Gateway | commit `7ce1d85` |
| Compose, Makefile, imagem `tools` | commit `849e674` |
| CI | commit `6c8728d` |
| ADRs, backlog e documentação da sprint | commit de documentação da sprint, tag `sprint-0` |

Resultado de `make test` ao fim da sprint:

| Pacote | Testes | Cobertura |
|---|---|---|
| ruff (lint + format) | — | OK |
| eh_auth | 11 | 100% |
| eh_db | 6 | 100% |
| eh_events | 13 | 100% |
| eh_http | 9 | 100% |
| eh_observability | 10 | 100% |
| eh_ui | 9 | 100% |
| api-gateway | 11 | 98% |

Stack no ar: `api-gateway` e `rabbitmq` *healthy*; `GET /services` já lista os
sete serviços de negócio (ainda `down`, pois são implementados nas próximas
sprints).

## Problemas técnicos encontrados e soluções

1. **Host sem GNU Make (Windows).** O enunciado assume `make` no host. Solução:
   o `Makefile` foi escrito para funcionar tanto em `sh` quanto em `cmd.exe`
   (somente comandos `docker`/`docker compose`, `$(CURDIR)` em vez de `$(PWD)`,
   sem aspas simples) e, durante a construção, os comandos equivalentes foram
   executados diretamente.
2. **Imagem `tools` sem Jinja2.** Os testes do `eh_ui` falharam na coleta
   (`ModuleNotFoundError: jinja2`). Solução: dependência adicionada a
   `scripts/requirements-dev.txt`.
3. **Headers duplicados no proxy.** O Starlette entrega os headers em minúsculas
   e o gateway acrescentava `X-Correlation-ID`/`X-Served-By` com outra caixa,
   gerando linhas duplicadas. Solução: `eh_http` passou a mesclar headers com
   `httpx.Headers` (comparação sem diferenciar maiúsculas) e o gateway usa chaves
   minúsculas.
4. **Formatação.** A primeira execução de `ruff format` reformatou 14 arquivos e
   apontou uma linha acima de 100 colunas; corrigido antes do commit.

## Retrospectiva

[PREENCHER: retrospectiva da equipe — o que foi bem, o que melhorar, ações]
