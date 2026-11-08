# ADR-002 — Python 3.12 + FastAPI em todos os serviços

**Status:** Aceito · **Sprint:** 0

## Contexto

A equipe é pequena e o projeto é intensivo (5 micro-sprints). O enunciado pede
OpenAPI em `/docs`, validação forte e código documentado.

## Decisão

Usar Python 3.12 e FastAPI em todos os serviços, pydantic v2 para validação,
SQLAlchemy 2 assíncrono + Alembic para PostgreSQL, uvicorn como servidor ASGI.

## Consequências

- (+) Uma única *stack* facilita o reuso por componentes (ADR-005).
- (+) OpenAPI gerado automaticamente em `/docs`.
- (+) Código assíncrono adequado a I/O (HTTP, AMQP, banco).
- (−) Diversidade tecnológica — uma das vantagens de microsserviços — não é
  explorada; aceitável dado o prazo.
