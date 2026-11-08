# Sprint 1 — Identidade e vagas

- **Período:** [PREENCHER: data/hora de início e fim — usar os timestamps do primeiro e do último commit da sprint (`git log sprint-0..sprint-1`)]
- **Duração planejada:** cerca de 2 horas
- **Tag:** `sprint-1`

## Meta da sprint

Permitir que estudantes e empresas se cadastrem, façam login com papéis e
mantenham seus perfis, e que empresas publiquem vagas (respeitando os limites
de jornada da Lei nº 11.788/2008) que os estudantes possam buscar — tudo pela
interface web, passando pelo API Gateway.

## Histórias selecionadas

| ID | História | SP |
|---|---|---|
| US-06 | Cadastro e login com papéis | 5 |
| US-07 | Perfil acadêmico do estudante | 3 |
| US-08 | Perfil da empresa concedente | 2 |
| US-09 | Publicar vaga com requisitos legais | 5 |
| US-10 | Buscar e filtrar vagas | 3 |
| US-11 | Encerrar vaga | 1 |
| | **Total** | **19** |

## Tarefas técnicas

| Tarefa | História | Estimativa |
|---|---|---|
| `user-service`: modelos, migração Alembic, registro/login (argon2 + JWT), `user.registered` | US-06 | 1,5 h |
| `user-service`: perfis de estudante e empresa, `profile.updated`, consulta em lote | US-07, US-08 | 1 h |
| `internship-service`: modelo, migração com *check constraints* de jornada, publicação, busca, estatísticas, encerramento | US-09, US-10, US-11 | 1,5 h |
| Testes de API dos dois serviços (SQLite em memória + `InMemoryPublisher`) | todas | 1 h |
| `web-frontend`: layout, login/cadastro, dashboard por papel, vagas, perfis, *toggle* de microsserviços | US-06, US-09, US-10 | 2 h |
| Testes do frontend com gateway falso (`httpx.MockTransport`) | — | 0,5 h |
| Compose: bancos `user-db` e `internship-db`, serviços e frontend com *healthchecks* | — | 0,5 h |

## Definition of Done

- [x] Código com *docstrings*.
- [x] Testes passando (`make test`).
- [x] `ruff` sem erros.
- [x] Serviços *healthy* no Compose (`user-service`, `internship-service`, `web-frontend`).
- [x] Documentação atualizada (ADR-007, PROGRESS.md, README).

## Review — o que foi entregue

| Entrega | Evidência |
|---|---|
| Correção no `eh_db` (timestamps com `eager_defaults`, v0.1.1) | commit `f731b67` |
| Correção no `eh_observability` (log de acesso único, v0.1.1) | commit `efbdb9f` |
| `user-service` | commit `e884abf` |
| `internship-service` | commit `59d6876` |
| `web-frontend` | commit `b4f8487` |
| Compose com os novos serviços | commit `fc8ccbb` |
| Documentação da sprint | commit de documentação, tag `sprint-1` |

Resultado de `make test` ao fim da sprint:

| Pacote | Testes | Cobertura |
|---|---|---|
| ruff | — | OK |
| componentes (6) | 59 | 100% |
| api-gateway | 11 | 98% |
| user-service | 16 | 97% |
| internship-service | 12 | 98% |
| web-frontend | 14 | 98% |

Verificação manual na stack real: cadastro e login de empresa pela API,
publicação de vaga (201, evento `internship.published` no log), vaga com
8 h/dia rejeitada (422), dashboard e lista de vagas no navegador com os
*badges* `internship-service` e o *toggle* "Mostrar microsserviços".

## Problemas técnicos encontrados e soluções

1. **`MissingGreenlet` ao ler `updated_at` depois de um UPDATE.** A coluna é
   preenchida pelo banco (`onupdate=func.now()`); o SQLAlchemy a expira após o
   *flush* e tenta recarregá-la de forma implícita, o que é proibido no modo
   assíncrono. Solução: `__mapper_args__ = {"eager_defaults": True}` no
   `TimestampMixin` do `eh_db` (busca via `RETURNING`), com teste de regressão
   e versão 0.1.1 do componente.
2. **Cobertura subestimada nos serviços assíncronos** (66% reportado em
   `api.py` com todos os testes passando). O SQLAlchemy assíncrono executa
   código dentro de *greenlets* e o `coverage` perdia o rastreamento. Solução:
   `concurrency = ["thread", "greenlet"]` em `[tool.coverage.run]`; a cobertura
   real é 97–98%.
3. **Log de acesso duplicado e ruidoso.** `configure_logging` reativava o
   *logger* `uvicorn.access`, anulando `--no-access-log` e registrando cada
   *healthcheck*. Solução: o componente silencia `uvicorn.access`, pois o
   `ObservabilityMiddleware` já registra cada requisição (exceto sondas).
   Versão 0.1.1 do `eh_observability`.
4. **Porta 8080 ocupada em IPv6 no host.** Um processo do WSL (`wslrelay`)
   escutava em `[::1]:8080`; `localhost` resolvia para ele e mostrava outra
   aplicação. Solução: acesso por `http://127.0.0.1:8080`, documentado no
   README; o CORS do gateway passou a aceitar as duas origens.
5. **Requisições com acentos rejeitadas (400) em teste manual.** O `curl` do
   Git Bash no Windows não enviava o corpo em UTF-8. Não era defeito do
   serviço; os testes manuais passaram a usar arquivo de corpo e o frontend
   (formulário HTML) envia UTF-8 corretamente.
6. **Barra de rolagem horizontal ao ligar o *toggle*.** O *checkbox* oculto
   herdava `width: 100%` com `position: absolute`. Solução: dimensões fixas e
   `position: relative` no rótulo.

## Retrospectiva

[PREENCHER: retrospectiva da equipe — o que foi bem, o que melhorar, ações]
