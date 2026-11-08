# ADR-005 — Reuso por componentes instaláveis com versão semântica

**Status:** Aceito · **Sprint:** 0

## Contexto

O enunciado exige a técnica "Componentes de Software". Sem ela, autenticação,
eventos, persistência, observabilidade e cliente HTTP seriam copiados em cada
serviço.

## Decisão

Criar seis componentes em `components/`, cada um um pacote Python independente
(`pyproject.toml` com versão semântica, interface pública explícita em
`__init__.py`, README com interfaces fornecida/requerida e testes com cobertura
≥ 80%): `eh_auth`, `eh_events`, `eh_db`, `eh_observability`, `eh_http`, `eh_ui`.
Os serviços instalam apenas os componentes de que precisam, por caminho, no
estágio *builder* do Dockerfile.

## Consequências

- (+) Interfaces explícitas e substituíveis (ex.: `IdempotencyStore` tem
  implementações SQL, Redis e Mongo).
- (+) Componentes sem dependência entre si: `eh_http` recebe um
  `header_provider` em vez de importar `eh_observability`.
- (+) Métricas de reuso calculáveis (`scripts/reuse_metrics.py`).
- (−) Mudança num componente exige *rebuild* das imagens que o usam; a versão
  semântica sinaliza mudanças incompatíveis.
