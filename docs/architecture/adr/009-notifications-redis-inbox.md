# ADR-009 — Notificações em Redis, alimentadas por todos os eventos

**Status:** Aceito · **Sprint:** 2

## Contexto

Cada transição do fluxo deve notificar os atores envolvidos. Notificações são
numerosas, de leitura frequente e de baixa criticidade (podem expirar).

## Decisão

- O `notification-service` consome **todos** os eventos (*binding* `#`).
- Uma função pura (`notices_for`) traduz cada evento em notificações para
  `user:<id>` ou para o papel inteiro (`role:coordinator`).
- Redis guarda listas por caixa (`inbox:*`, limitadas a 200 itens), conjuntos
  de lidas por usuário (`read:<id>`) e marcadores de idempotência com TTL
  (`processed:<event_id>`, 7 dias).
- Notificações diretas (`POST /notifications`) atendem a ferramenta
  `send_notification` dos agentes.

## Consequências

- (+) Produtores não conhecem as notificações: incluir uma nova regra só muda
  `notices_for`.
- (+) A caixa da coordenação é compartilhada, mas o estado de leitura é
  individual.
- (−) Sem garantia de durabilidade forte (AOF ligado mitiga); aceitável para
  notificações.
