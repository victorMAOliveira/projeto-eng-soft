# ADR-003 — API Gateway próprio em Python

**Status:** Aceito · **Sprint:** 0

## Contexto

O item 6.2 do modelo de relatório exige código documentado do API Gateway.
Produtos prontos (Kong, Traefik) resolveriam o roteamento por configuração, sem
código a apresentar.

## Decisão

Implementar o `api-gateway` em FastAPI com: tabela de rotas por prefixo,
validação de JWT e política de papéis na borda, encaminhamento via
`eh_http.ResilientClient` (timeout, *retry* com *backoff*, *circuit breaker* por
upstream), propagação de *correlation-id* e o endpoint `GET /services`, que
agrega `/ready` e `/version` de todos os serviços.

## Consequências

- (+) Comportamento totalmente explicável e testável (testes com
  `httpx.MockTransport`).
- (+) Erros de upstream viram 503 com o nome do serviço, o que permite à
  interface degradar graciosamente.
- (−) Desempenho inferior a um proxy nativo; irrelevante para a escala do
  projeto.
- (−) Os serviços revalidam o JWT (defesa em profundidade), o que duplica uma
  verificação barata.
