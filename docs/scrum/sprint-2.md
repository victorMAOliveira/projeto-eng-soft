# Sprint 2 — Candidaturas e documentos

- **Período:** [PREENCHER: data/hora de início e fim — usar os timestamps do primeiro e do último commit da sprint (`git log sprint-1..sprint-2`)]
- **Duração planejada:** cerca de 2 horas
- **Tag:** `sprint-2`

## Meta da sprint

Fechar o núcleo do fluxo principal: candidatura, análise e aprovação pela
empresa com validação das regras da Lei nº 11.788/2008, geração automática do
TCE em PDF, aprovação pela coordenação ativando o estágio (saga coreografada
via RabbitMQ), relatórios com versões e notificações a cada transição.

## Histórias selecionadas

| ID | História | SP |
|---|---|---|
| US-12 | Candidatar-se a uma vaga | 3 |
| US-13 | Analisar, aprovar ou rejeitar candidaturas | 5 |
| US-14 | Validar regras da Lei nº 11.788/2008 | 5 |
| US-15 | Kanban de candidaturas por status | 3 |
| US-16 | TCE gerado automaticamente em PDF | 8 |
| US-17 | Coordenação aprova o TCE e ativa o estágio | 3 |
| US-18 | Relatórios de atividades com versões | 5 |
| US-19 | Notificação a cada transição | 5 |
| | **Total** | **37** |

## Tarefas técnicas

| Tarefa | História | Estimativa |
|---|---|---|
| Domínio puro: máquina de estados e regras legais (jornada, 2 anos/PcD, seguro, relatório semestral, elegibilidade) | US-13, US-14 | 1 h |
| `application-service`: modelos, migração, API, chamadas REST resilientes a vagas/usuários, *handlers* da saga | US-12, US-13 | 2 h |
| `eh_events` 0.2.0: campos opcionais de exibição nos contratos | US-19 | 0,25 h |
| `document-service`: *ports* (Mongo/memória), PDF com ReportLab, *preview* com pypdfium2, aprovação, relatórios com versões | US-16, US-17, US-18 | 2 h |
| `notification-service`: regras evento → notificação, caixas no Redis, idempotência | US-19 | 1 h |
| Frontend: candidatar-se, kanban, detalhe com histórico, formulário de aprovação, TCE, relatórios, notificações, sino | US-15..US-19 | 2 h |
| Compose: PostgreSQL de candidaturas, MongoDB, Redis, volume de arquivos | — | 0,5 h |
| Teste de fumaça da saga contra a stack real | — | 0,25 h |

## Definition of Done

- [x] Código com *docstrings*.
- [x] Testes passando (`make test`): 114 testes no `application-service`, incluindo as 81 combinações da máquina de estados.
- [x] `ruff` sem erros.
- [x] Serviços *healthy* no Compose (13 containers).
- [x] Documentação atualizada (ADR-008, ADR-009, PROGRESS.md).

## Review — o que foi entregue

| Entrega | Evidência |
|---|---|
| Contratos de eventos 0.2.0 | commit `e5bc7e9` |
| `application-service` (máquina de estados, regras legais, saga) | commit `5f596d9` |
| `document-service` (TCE em PDF, aprovação, relatórios) | commit `da3014e` |
| `notification-service` | commit `df22452` |
| Telas do frontend | commit `f85c5a7` |
| Compose com os novos serviços e bancos | commit `943854e` |
| Documentação da sprint | commit de documentação, tag `sprint-2` |

Resultado de `make test` ao fim da sprint:

| Pacote | Testes | Cobertura |
|---|---|---|
| ruff | — | OK |
| componentes (6) | 59 | 100% |
| api-gateway | 11 | 98% |
| user-service | 16 | 97% |
| internship-service | 12 | 98% |
| application-service | 114 | 97% |
| document-service | 12 | 92% |
| notification-service | 15 | 95% |
| web-frontend | 22 | 98% |

Teste de fumaça contra a stack real (via gateway): cadastro de empresa,
estudante e coordenação; vaga; perfil; candidatura (201,
`X-Served-By: application-service`); análise; aprovação com seguro → TCE gerado
pelo `document-service` e candidatura em `agreement_pending`; PDF baixado
(`%PDF-`); aprovação da coordenação → `active` com próximo relatório em 6 meses;
relatório enviado (201); notificações recebidas pelos três papéis; tentativa de
desistir de estágio ativo → **409**.

## Problemas técnicos encontrados e soluções

1. **`MissingGreenlet` ao serializar uma candidatura recém-criada.** O
   relacionamento `placement` nunca tinha sido carregado e o pydantic tentou
   lê-lo, disparando *lazy load* assíncrono. Solução: inicializar
   `placement=None` explicitamente na criação (relacionamentos de objetos
   carregados usam `lazy="selectin"`).
2. **Texto das notificações sem nomes.** Os eventos `agreement.*` e
   `report.submitted` não traziam nomes legíveis. Solução: campos opcionais
   nos contratos (`student_name`, `internship_title`...), mudança compatível
   (`eh_events` 0.2.0, `schema_version` mantido em 1).
3. **Pré-visualização do TCE em branco em capturas de tela.** A imagem usava
   `loading="lazy"` e não era carregada antes da captura. Solução: remover o
   carregamento preguiçoso dessa imagem.
4. **Quatro linhas acima de 100 colunas** apontadas pelo `ruff` (textos legais
   do PDF e mensagens) — quebradas antes do commit.

## Retrospectiva

[PREENCHER: retrospectiva da equipe — o que foi bem, o que melhorar, ações]
