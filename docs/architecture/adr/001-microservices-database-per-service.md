# ADR-001 — Microsserviços com Database per Service

**Status:** Aceito · **Sprint:** 0

## Contexto

O enunciado exige a técnica de reuso "Microservices". O domínio de estágios tem
subdomínios com ciclos de mudança e requisitos de dados diferentes: identidade,
vagas, candidaturas/estágio (regras legais), documentos (arquivos binários),
notificações (alto volume, baixa durabilidade), recomendação (modelo de leitura)
e agentes de IA (histórico de execuções).

## Decisão

- Decompor o sistema em 8 serviços alinhados a esses subdomínios (*decompose by
  subdomain*, Richardson, 2018), mais o frontend.
- Cada serviço é dono exclusivo do seu banco, em um container próprio
  (*Database per Service*): 5 PostgreSQL, 1 MongoDB e 1 Redis.
- Nenhum serviço acessa o banco de outro: os dados de outro contexto chegam por
  REST (consulta síncrona) ou por eventos (cópia local alimentada por eventos).

## Consequências

- (+) Autonomia de implantação e escolha do banco adequado a cada contexto.
- (+) Falha de um banco afeta apenas um serviço (degradação graciosa).
- (−) Consistência eventual entre serviços: exige eventos idempotentes e saga.
- (−) Mais containers para operar; mitigado por Compose com *healthchecks*.
