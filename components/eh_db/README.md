# eh_db

Componente de persistência dos serviços com PostgreSQL: *engine* e sessão
assíncronas do SQLAlchemy 2, repositório genérico, *helper* de migrações
Alembic e a tabela de idempotência de eventos.

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `Base` | classe | `DeclarativeBase` com convenção de nomes de *constraints* (migrações estáveis). |
| `TimestampMixin` | mixin | Colunas `created_at` e `updated_at` mantidas pelo banco. |
| `Database(url)` | classe | `engine`, `session()` (commit/rollback automático), `get_session` (dependência FastAPI), `ping()` (prontidão), `create_all()` (testes), `dispose()`. |
| `BaseRepository[Model]` | classe genérica | `get`, `list` (filtros de igualdade, paginação, ordenação), `count`, `add`, `delete`. |
| `ProcessedEvent` | modelo | Tabela `processed_events` (deduplicação por `event_id`). |
| `SqlIdempotencyStore(db)` | classe | Implementa o protocolo de idempotência do `eh_events` (`seen`, `mark`). |
| `run_migrations(metadata, url=None)` | função | Corpo do `alembic/env.py` de cada serviço (modo *offline* e *online* assíncrono). |

## Interface requerida

- `SQLAlchemy[asyncio] 2.0`, `alembic >= 1.13`.
- Driver do banco: `asyncpg` (extra `postgres`) em produção, `aiosqlite` nos testes.
- Variável `DATABASE_URL` (ou parâmetro `url`).

## Exemplo de uso

```python
from eh_db import Base, BaseRepository, Database

class Internship(Base): ...

class InternshipRepository(BaseRepository[Internship]):
    model = Internship

db = Database(settings.database_url)
async with db.session() as session:
    vagas = await InternshipRepository(session).list(status="open", limit=20)
```

`alembic/env.py` de cada serviço:

```python
from eh_db import run_migrations
from user_service.models import Base
run_migrations(Base.metadata)
```

## Serviços que reutilizam

`user-service`, `internship-service`, `application-service`,
`recommendation-service` e `agent-service` (os cinco serviços com PostgreSQL).
