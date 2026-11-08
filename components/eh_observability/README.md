# eh_observability

Componente de observabilidade do EstágioHub: log estruturado em JSON,
propagação de *correlation-id*, header `X-Served-By` e a Health Check API
(`/health`, `/ready`, `/version`).

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `configure_logging(service_name, level)` | função | Direciona todo o `logging` (inclusive o do uvicorn) para JSON em stdout. |
| `JsonFormatter` | classe | Formatter que serializa cada registro em uma linha JSON, com `service`, `correlation_id` e campos `extra`. |
| `ObservabilityMiddleware` | middleware ASGI | Gera/propaga `X-Correlation-ID`, adiciona `X-Served-By` e registra log de acesso. |
| `get_correlation_id()` / `set_correlation_id()` | funções | Leem/definem o id de correlação do contexto atual (`contextvars`). |
| `create_health_router(service, version, checks, database)` | função | Cria o router com `/health`, `/ready` (executa as verificações) e `/version`. |
| `setup_observability(app, service, version, checks, database)` | função | Instala middleware e router em uma chamada. |
| `Check` | tipo | `Callable[[], Awaitable[bool]]` usado nas verificações de prontidão. |

## Interface requerida

- `fastapi >= 0.115` (e, por consequência, `starlette`).

## Exemplo de uso

```python
from fastapi import FastAPI
from eh_observability import configure_logging, setup_observability

configure_logging("user-service")
app = FastAPI()
setup_observability(
    app, "user-service", "1.0.0",
    checks={"database": db.ping, "broker": publisher.is_connected},
    database="PostgreSQL",
)
```

## Serviços que reutilizam

Todos: `api-gateway`, `user-service`, `internship-service`, `application-service`,
`document-service`, `notification-service`, `recommendation-service`,
`agent-service` e `web-frontend`.

## Testes

```bash
pip install -e ".[test]" && pytest --cov=eh_observability
```
