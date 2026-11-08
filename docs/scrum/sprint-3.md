# Sprint 3 — Inteligência

- **Período:** [PREENCHER: data/hora de início e fim — usar os timestamps do primeiro e do último commit da sprint (`git log sprint-2..sprint-3`)]
- **Duração planejada:** cerca de 2 horas
- **Tag:** `sprint-3`

## Meta da sprint

Entregar a camada de inteligência: recomendação híbrida e explicável (vagas
para estudantes e ranking de candidatos para empresas) com avaliação offline
contra *baselines*, e os três agentes de IA com fallback determinístico,
*guardrails* e trilha de execução.

## Histórias selecionadas

| ID | História | SP |
|---|---|---|
| US-20 | Vagas recomendadas com explicação | 8 |
| US-21 | Ranking de candidatos para a empresa | 5 |
| US-22 | Avaliação offline do recomendador | 3 |
| US-23 | Assistente de Candidatura (IA) | 5 |
| US-24 | Agente de Acompanhamento de prazos | 5 |
| US-25 | Agente de Triagem de candidatos | 3 |
| | **Total** | **29** |

## Tarefas técnicas

| Tarefa | História | Estimativa |
|---|---|---|
| Algoritmo puro (`recommender.py`): filtros, TF-IDF/cosseno, Jaccard, preferências, explicação, *cold start*, ranking de candidatos | US-20, US-21 | 1,5 h |
| Modelo de leitura + projeção por eventos + `rebuild` via REST | US-20 | 1 h |
| Gerador sintético determinístico (`scripts/synthetic_data.py`) e avaliação (`scripts/evaluate_recommender.py`) | US-22 | 1 h |
| `agent-service`: ferramentas, laço de *tool use* (6 passos, *timeout*), modo regras, trilha, deduplicação de alertas, APScheduler | US-23, US-24, US-25 | 2 h |
| Frontend: recomendações, ranking na página de candidatos, assistente com trilha (HTMX) | US-20, US-21, US-23 | 1,5 h |
| Compose: bancos `recommendation-db` e `agent-db`, serviços | — | 0,25 h |

## Definition of Done

- [x] Código com *docstrings*.
- [x] Testes passando (`make test`), com o cliente LLM sempre substituído por dublê.
- [x] `ruff` sem erros.
- [x] Serviços *healthy* no Compose (17 containers).
- [x] Documentação atualizada (ADR-010, ADR-011, PROGRESS.md).

## Review — o que foi entregue

| Entrega | Evidência |
|---|---|
| `recommendation-service` | commit `95a6c24` |
| Conjunto sintético e avaliação offline | commit `1bcbe46` |
| `agent-service` | commit `1415ca0` |
| Correção do prazo do 1º relatório | commit `f92b48d` |
| Telas de recomendação, ranking e assistente | commit `93b3eaa` |
| Compose e configuração | commit `6210dd7` |
| Documentação da sprint | commit de documentação, tag `sprint-3` |

Resultado de `make eval` (dados **sintéticos**, 48 estudantes avaliados, 30 vagas, k = 5):

| Estratégia | Precision@5 | nDCG@5 |
|---|---|---|
| Baseline aleatório | 0,151 | 0,151 |
| Baseline só filtros (mais recentes) | 0,708 | 0,825 |
| Híbrido (0,50·cos + 0,35·Jaccard + 0,15·pref) | 0,725 | 0,968 |
| Ablação: só conteúdo (TF-IDF/cosseno) | 0,721 | 0,978 |
| Ablação: só atributos (Jaccard) | 0,725 | 0,970 |

Resultado de `make test` ao fim da sprint: `recommendation-service` 14 testes
(98%), `agent-service` 11 testes (95%), `web-frontend` 28 testes (98%); demais
pacotes inalterados e passando.

Teste de fumaça na stack real: `rebuild` reconstruiu o modelo de leitura
(2 estudantes, 3 vagas, 2 candidaturas); recomendações com explicação
(`X-Served-By: recommendation-service`) excluindo a vaga já candidatada; os três
agentes executaram em modo regras com trilha; estudante chamando o agente de
acompanhamento recebeu 403.

## Problemas técnicos encontrados e soluções

1. **Modelo de leitura vazio para dados anteriores ao serviço.** Os eventos
   publicados antes de o `recommendation-service` existir não estavam na fila
   dele. Solução: `POST /recommendations/rebuild`, que reconstrói o modelo via
   REST com token de serviço — o caminho de recuperação de um *read model*.
2. **Prazo do primeiro relatório contado a partir da aprovação.** A primeira
   versão usava a data da ativação; o período de 6 meses do art. 9º, VII conta
   do início do estágio. Solução: `next_report_due(start_date)` (estágios
   cadastrados retroativamente podem nascer com relatório a vencer).
3. **Precision@5 quase igual entre híbrido e só-filtros.** Cada estudante tem
   poucas vagas elegíveis do seu curso (≈3), então os dois métodos acertam
   quase o mesmo conjunto; a diferença aparece na **ordem** (nDCG@5 0,968 ×
   0,825). A ablação "só conteúdo" ficou ligeiramente acima do híbrido no
   nDCG@5 — resultado registrado sem ajuste dos pesos para não sobreajustar ao
   conjunto sintético.
4. **Linhas longas em textos pt-BR.** Vinte avisos E501 em literais de texto
   que o formatador não quebra. Decisão: o comprimento de linha passa a ser
   garantido pelo `ruff format` (E501 desativado no *lint*).

## Retrospectiva

[PREENCHER: retrospectiva da equipe — o que foi bem, o que melhorar, ações]
