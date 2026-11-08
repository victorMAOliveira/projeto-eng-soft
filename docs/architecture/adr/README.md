# Architecture Decision Records

Formato baseado em Michael Nygard ("Documenting Architecture Decisions"):
contexto, decisão, consequências e status. A data de cada decisão é a do
commit que introduziu o ADR (`git log --follow docs/architecture/adr/<arquivo>`).

| ADR | Título | Sprint | Status |
|---|---|---|---|
| [001](001-microservices-database-per-service.md) | Microsserviços com Database per Service | 0 | Aceito |
| [002](002-python-fastapi-stack.md) | Python 3.12 + FastAPI em todos os serviços | 0 | Aceito |
| [003](003-custom-python-api-gateway.md) | API Gateway próprio em Python | 0 | Aceito |
| [004](004-rabbitmq-events-choreographed-saga.md) | Eventos no RabbitMQ e saga coreografada | 0 | Aceito |
| [005](005-reuse-via-installable-components.md) | Reuso por componentes instaláveis com versão semântica | 0 | Aceito |
| [006](006-tooling-in-containers.md) | Ferramentas em containers e host enxuto | 0 | Aceito |
| [007](007-server-side-rendering-htmx.md) | Frontend renderizado no servidor com Jinja2 + HTMX | 1 | Aceito |
| [008](008-documents-mongodb-and-volume.md) | Documentos: MongoDB para metadados e volume para arquivos | 2 | Aceito |
| [009](009-notifications-redis-inbox.md) | Notificações em Redis, alimentadas por todos os eventos | 2 | Aceito |
| [010](010-hybrid-explainable-recommender.md) | Recomendador híbrido, explicável e determinístico | 3 | Aceito |
| [011](011-ai-agents-with-rules-fallback.md) | Agentes de IA com tool use e fallback em modo regras | 3 | Aceito |
