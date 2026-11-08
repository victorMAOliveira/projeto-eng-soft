# eh_events

Componente de comunicação assíncrona do EstágioHub: contratos de eventos
versionados (pydantic) e *publisher*/*consumer* assíncronos sobre RabbitMQ
(aio-pika), com *retry*, idempotência e *dead-letter queue*.

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `Event` | modelo | Envelope: `event_id`, `event_type`, `occurred_at`, `schema_version`, `producer`, `correlation_id`, `payload`. |
| `EventType` | enum | As 10 *routing keys* (`user.registered`, ..., `report.due_soon`). |
| `UserRegistered`, `ProfileUpdated`, `InternshipPublished`, `InternshipClosed`, `ApplicationSubmitted`, `ApplicationStatusChanged`, `PlacementTerms`, `AgreementGenerated`, `AgreementApproved`, `ReportSubmitted`, `ReportDueSoon` | modelos | Contrato do `payload` de cada evento. |
| `make_event`, `parse_event`, `typed_payload` | funções | Criam, validam e tipam eventos. |
| `EventPublisher(url, service_name)` | classe | `connect()`, `publish(type, payload)`, `is_connected()`, `close()`; mensagens persistentes no *topic exchange* `estagiohub.events`. |
| `InMemoryPublisher` | classe | Dublê de teste com a mesma interface (`events`, `of_type`). |
| `Publisher` | protocolo | O que os serviços exigem de um *publisher*. |
| `EventConsumer(url, queue_name, routing_keys, handler, idempotency)` | classe | Declara fila durável + DLQ, deduplica por `event_id`, faz *retry* com *backoff* e envia à DLQ após `max_retries`. |
| `IdempotencyStore` / `InMemoryIdempotencyStore` | protocolo / classe | `seen(event_id)` e `mark(event_id, type)`. |

Topologia declarada pelo consumidor:

```
estagiohub.events (topic) ──routing keys──▶ <serviço>.events
<serviço>.events ──x-dead-letter-exchange──▶ estagiohub.events.dlx ──▶ <serviço>.events.dlq
```

## Interface requerida

- `pydantic >= 2.7`, `aio-pika >= 9.4`, um broker RabbitMQ (AMQP 0-9-1).
- Uma implementação de `IdempotencyStore` (ex.: `eh_db.SqlIdempotencyStore`,
  ou a de Redis/Mongo do serviço).

## Exemplo de uso

```python
from eh_events import EventConsumer, EventPublisher, EventType, ApplicationSubmitted

publisher = EventPublisher(settings.rabbitmq_url, service_name="application-service")
await publisher.connect()
await publisher.publish(EventType.APPLICATION_SUBMITTED, ApplicationSubmitted(...))

consumer = EventConsumer(
    settings.rabbitmq_url, queue_name="notification-service.events",
    routing_keys=["#"], handler=handle_event, idempotency=RedisIdempotencyStore(redis),
)
await consumer.start()
```

## Serviços que reutilizam

`user-service`, `internship-service`, `application-service`,
`document-service`, `notification-service`, `recommendation-service` e
`agent-service`.
