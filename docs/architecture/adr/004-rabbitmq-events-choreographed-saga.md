# ADR-004 — Eventos no RabbitMQ e saga coreografada

**Status:** Aceito · **Sprint:** 0

## Contexto

O fluxo aprovação → TCE → aprovação da coordenação → estágio ativo atravessa
`application-service` e `document-service`, cada um com seu banco. Transações
distribuídas (2PC) não são viáveis entre PostgreSQL e MongoDB.

## Decisão

- *Topic exchange* durável `estagiohub.events`; a *routing key* é o tipo do
  evento (`application.status_changed`...).
- Contratos versionados (`schema_version`) no componente `eh_events`, com
  *event-carried state transfer*: o *payload* leva os dados de que o consumidor
  precisa.
- Cada consumidor tem fila durável própria, deduplicação por `event_id`,
  *retry* com *backoff* e *dead-letter queue* (`<fila>.dlq`).
- A saga é **coreografada**: cada serviço reage a eventos e publica o próximo;
  não há orquestrador central.

## Consequências

- (+) Baixo acoplamento: o produtor não conhece os consumidores.
- (+) Novos consumidores (notificações, recomendação) sem alterar produtores.
- (−) O fluxo fica distribuído no código; mitigado com o diagrama de sequência
  da saga e o *correlation-id* nos logs.
- (−) Consistência eventual: a interface mostra estados intermediários
  (`approved` antes de `agreement_pending`).
