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
