# eh_http

Cliente HTTP resiliente para a comunicação síncrona (REST) entre os
microsserviços do EstágioHub: *timeout*, *retry* com *backoff* exponencial e
*circuit breaker* simples por upstream.

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `ResilientClient(base_url, name, timeout, retries, backoff, breaker, header_provider)` | classe | Envolve `httpx.AsyncClient`; métodos `request`, `get`, `post`, `put`, `aclose`. |
| `CircuitBreaker(failure_threshold, recovery_timeout)` | classe | Estados `closed → open → half_open`; `allow_request`, `record_success`, `record_failure`. |
| `CircuitState` | enum | Estados do breaker. |
| `CircuitOpenError` | exceção | O circuito está aberto; nenhuma requisição foi enviada (*fail fast*). |
| `UpstreamUnavailableError` | exceção | Todas as tentativas falharam na camada de transporte. |

Política de *retry*: métodos idempotentes (GET, PUT, DELETE...) repetem em
erros de transporte e em 502/503/504; POST/PATCH só repetem quando a conexão
nem chegou a ser estabelecida — assim, nenhuma operação é aplicada duas vezes.

## Interface requerida

- `httpx >= 0.27`.
- Opcional: um `header_provider` (ex.: `eh_observability.get_correlation_id`)
  para propagar o *correlation-id* sem acoplamento direto entre componentes.

## Exemplo de uso

```python
from eh_http import ResilientClient, CircuitOpenError, UpstreamUnavailableError
from eh_observability import get_correlation_id

users = ResilientClient(
    "http://user-service:8000", name="user-service", timeout=3, retries=2,
    header_provider=lambda: {"X-Correlation-ID": get_correlation_id()},
)
try:
    response = await users.get("/profiles/students/42")
except (CircuitOpenError, UpstreamUnavailableError):
    ...  # degradação graciosa
```

## Serviços que reutilizam

`api-gateway`, `application-service`, `recommendation-service`,
`agent-service` e `web-frontend`.
