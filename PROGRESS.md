# PROGRESS — EstágioHub

Registro de andamento por sprint (feito, pendente, decisões, problemas). Para
retomar uma sessão interrompida, comece por aqui.

## Sprint 0 — Fundação

**Feito**
- Repositório, `.gitignore`, `.gitattributes` (LF), `.editorconfig`, configuração do `ruff`.
- Seis componentes em `components/` com `pyproject.toml` (0.1.0), interface pública, README e testes
  (`eh_auth`, `eh_events`, `eh_db`, `eh_observability`, `eh_http`, `eh_ui`), cobertura 100% em todos.
- `api-gateway`: rotas por prefixo, JWT + política de papéis, proxy resiliente, `GET /services`, `GET /routes`.
- `docker-compose.yml` com RabbitMQ (painel na 15672), gateway (8000) e o serviço `tools` (profile).
- `Makefile` (só chama docker), `scripts/make_env.py`, imagem `tools`, `scripts/run_tests.py`.
- CI no GitHub Actions: ruff, `make test`, `docker compose build`.
- ADRs 001–006; Product Backlog com 31 histórias.

**Decisões**
- Host sem GNU Make: o Makefile foi escrito para `sh` e `cmd.exe`; durante a construção os comandos
  equivalentes foram executados diretamente (`docker compose run ...`).
- Componentes sem dependências entre si (`eh_http` recebe `header_provider`).
- Consumidores com `prefetch=1` para processar eventos em ordem.

**Problemas encontrados**
- `make` ausente no host Windows (ver decisões).
- Imagem `tools` sem Jinja2: testes do `eh_ui` falharam na coleta → dependência adicionada.
- Headers duplicados por diferença de caixa (`x-correlation-id` vs `X-Correlation-ID`) ao repassar
  requisições no gateway → `eh_http` passou a mesclar com `httpx.Headers` (case-insensitive) e o
  gateway usa chaves minúsculas.
- Primeira execução do `ruff format` reformatou 14 arquivos e acusou uma linha longa → corrigido.

**Pendente (próximas sprints)**
- Sprint 1: `user-service`, `internship-service`, frontend com login e vagas.

## Sprint 1 — Identidade e vagas

**Feito**
- `user-service`: registro (argon2), login (JWT com papel), `/users/me`, perfis de estudante e empresa,
  consulta em lote; eventos `user.registered` e `profile.updated`. Coordenação só é cadastrada com token
  de serviço/coordenação.
- `internship-service`: publicação com validação legal (6 h/dia, 30 h/semana, também como *check
  constraint*), busca com filtros e paginação, estatísticas, encerramento; eventos
  `internship.published` e `internship.closed`.
- `web-frontend`: login/cadastro, dashboard por papel, lista/detalhe/criação de vagas (busca com HTMX),
  perfis, *toggle* "Mostrar microsserviços" e *badges* `X-Served-By`. HTMX 2.0.4 empacotado localmente.
- Compose com `user-db`, `internship-db`, os dois serviços e o frontend (porta 8080).
- `eh_db` 0.1.1 e `eh_observability` 0.1.1 (correções); ADR-007.

**Decisões**
- JWT em cookie HttpOnly; o frontend não valida o token (não conhece o segredo), só lê as *claims*.
- Eventos publicados somente após o `commit` da transação (sem *outbox*; limitação registrada).

**Problemas encontrados** — ver `docs/scrum/sprint-1.md` (greenlet/`updated_at`, cobertura com greenlet,
log de acesso, porta 8080 em IPv6 no host, acentos no curl do Git Bash, *overflow* do *toggle*).

**Pendente**
- Sprint 2: `application-service`, `document-service`, `notification-service`, saga do TCE.

## Sprint 2 — Candidaturas e documentos

**Feito**
- `application-service`: máquina de estados completa (409 em transição inválida), regras legais (6 h/30 h,
  2 anos cumulativos na mesma concedente exceto PcD, seguro obrigatório, relatório a cada 6 meses,
  elegibilidade por curso/período/disponibilidade), histórico de transições, `/placements` com prazos;
  consome `agreement.generated`, `agreement.approved`, `report.submitted`.
- `document-service`: TCE em PDF (ReportLab) com cláusulas da lei, *preview* PNG (pypdfium2), aprovação
  pela coordenação, relatórios com versões (PDF ≤ 5 MB) — MongoDB + volume.
- `notification-service`: consome `#`, caixas por usuário e por papel no Redis, estado de leitura por usuário.
- Saga coreografada validada ponta a ponta contra a stack real.
- Frontend: candidatar-se, kanban, detalhe com linha do tempo, aprovação com termos, TCE com *preview*,
  relatórios, notificações e sino com contador (HTMX).
- ADR-008 e ADR-009; `eh_events` 0.2.0.

**Decisões**
- Regras legais em funções puras (`domain.py`) para teste exaustivo; serviços só orquestram.
- Seguro verificado em dois serviços (defesa em profundidade).

**Problemas encontrados** — ver `docs/scrum/sprint-2.md`.

**Pendente**
- Sprint 3: `recommendation-service` (+ avaliação offline) e `agent-service`.

## Sprint 3 — Inteligência

**Feito**
- `recommendation-service`: modelo de leitura por eventos, algoritmo híbrido explicável e determinístico
  (filtros + TF-IDF/cosseno + Jaccard + preferências; *cold start* por recência/popularidade), ranking de
  candidatos, `rebuild` via REST.
- `scripts/synthetic_data.py` (dados sintéticos com rótulos por trilha latente) e
  `scripts/evaluate_recommender.py` (precision@5, nDCG@5, *baselines* e ablações).
- `agent-service`: Assistente de Candidatura, Agente de Acompanhamento (APScheduler + sob demanda, publica
  `report.due_soon`) e Agente de Triagem; Claude via SDK oficial com laço de *tool use* de até 6 passos e
  *timeout*; fallback em modo regras; trilha de execução persistida.
- Frontend: recomendações com explicação, ranking na página de candidatos, assistente com trilha (HTMX),
  selo "IA em modo regras", top 3 no dashboard do estudante.
- ADR-010 e ADR-011.

**Decisões**
- Pesos 0,50/0,35/0,15 mantidos (não ajustados ao conjunto sintético).
- Agentes não têm ferramenta de escrita sobre candidaturas (decisão sempre humana).

**Problemas encontrados** — ver `docs/scrum/sprint-3.md`.

**Pendente**
- Sprint 4: tela de status, legenda de serviços, seed, e2e, prints, relatório, guia de estudo.
