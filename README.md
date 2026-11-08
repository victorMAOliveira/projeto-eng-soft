# EstágioHub

Sistema de gerenciamento de estágios universitários (Lei nº 11.788/2008)
construído com **microsserviços**, **componentes de software** e **agentes de IA**.

> Projeto da disciplina Engenharia de Software — Universidade Federal de
> Alagoas, Instituto de Computação. Professor: Arturo Hernandez Dominguez.
> Equipe: Victor Moura Amaral de Oliveira (Product Owner) e Lorenzo Holanda
> (Scrum Master). Repositório: <https://github.com/victorMAOliveira/projeto-eng-soft>.

O sistema cobre o ciclo completo: a empresa publica a vaga, o estudante recebe
recomendações explicadas e se candidata, a empresa aprova com os termos do
estágio, o **Termo de Compromisso (TCE)** é gerado em PDF, a coordenação
aprova, o estágio fica ativo, o estudante envia relatórios e todos recebem
notificações a cada transição.

## Executar em 3 comandos

Pré-requisitos: Docker (com Compose v2), Git e GNU Make. Testes, seed, prints e
relatório rodam em containers — nada mais precisa ser instalado.

```bash
make env    # cria .env a partir de .env.example e gera segredos aleatórios
make up     # constrói e sobe os 17 containers, esperando todos ficarem healthy
make seed   # carrega os dados de demonstração (sintéticos) via API Gateway
```

| Endereço | O quê |
|---|---|
| <http://localhost:8080> | Interface web |
| <http://localhost:8000/services> | Saúde agregada de todos os microsserviços (API Gateway) |
| <http://localhost:15672> | Painel do RabbitMQ (usuário `estagiohub`, senha `RABBITMQ_PASSWORD` do `.env`) |

> Se `localhost:8080` abrir outra aplicação, algum processo do host (por
> exemplo, um servidor dentro do WSL) está ocupando a porta em IPv6 (`::1`).
> Use <http://127.0.0.1:8080>.

## Usuários de demonstração (fictícios)

| Papel | E-mail | Senha |
|---|---|---|
| Coordenação de estágio | `coordenacao@ufal.test` | `Coord@2026` |
| Empresa concedente | `rh@techsolucoes.test` | `Empresa@2026` |
| Estudante (perfil completo) | `estudante@ufal.test` | `Estudante@2026` |
| Estudante sem perfil (*cold start*) | `calouro@ufal.test` | `Estudante@2026` |
| Demais 49 estudantes e 7 empresas | ver `data/synthetic/dataset.json` | `Demo@2026` |

Todos os nomes, empresas e documentos são fictícios (Faker pt_BR, semente fixa).

## Alvos do Makefile

| Comando | O que faz |
|---|---|
| `make env` | Cria `.env` e gera `JWT_SECRET` e senhas aleatórias (idempotente). |
| `make up` / `make down` | Sobe (com *build* e espera *healthy*) / para a stack. |
| `make clean` | Remove containers, volumes e redes. |
| `make seed` | Dados de demonstração via gateway (idempotente). |
| `make test` | `ruff` + testes unitários e de API de componentes, serviços e frontend. |
| `make e2e` | Fluxo principal completo via gateway contra a stack. |
| `make eval` | Avaliação offline do recomendador e métricas de reuso. |
| `make screenshots` | Prints do fluxo pela própria interface (Playwright) e de degradação. |
| `make report` | Diagramas Mermaid → PNG, relatório `.docx` e `.pdf` em `docs/relatorio/build/`. |
| `make all` | Tudo acima, em ordem. |

## Agentes de IA

Preencha `ANTHROPIC_API_KEY` no `.env` para usar o Claude (modelo em
`LLM_MODEL`, padrão `claude-haiku-5-5`). Sem a chave, os agentes funcionam em
**modo regras** com a mesma API, e a interface mostra o selo
"IA em modo regras".

## Arquitetura

| Serviço | Responsabilidade | Banco |
|---|---|---|
| `api-gateway` | Entrada única (8000): rotas, JWT/papéis, resiliência, `GET /services` | — |
| `user-service` | Contas, papéis, JWT, perfis | PostgreSQL |
| `internship-service` | Vagas | PostgreSQL |
| `application-service` | Candidaturas, máquina de estados, regras legais | PostgreSQL |
| `document-service` | TCE em PDF, relatórios com versões | MongoDB + volume |
| `notification-service` | Caixa de notificações (consome todos os eventos) | Redis |
| `recommendation-service` | Recomendação híbrida explicável (modelo de leitura) | PostgreSQL |
| `agent-service` | Agentes de IA com fallback | PostgreSQL |
| `web-frontend` | Interface (8080), FastAPI + Jinja2 + HTMX | — |
| `rabbitmq` | *Topic exchange* `estagiohub.events` + DLQ (painel 15672) | — |

Componentes reutilizáveis em `components/`: `eh_auth`, `eh_events`, `eh_db`,
`eh_observability`, `eh_http`, `eh_ui` (cada um com README próprio).

## Estrutura

```
components/        componentes de software (pacotes Python instaláveis)
services/          api-gateway e os sete microsserviços
frontend/web/      interface web
scripts/           seed, e2e, avaliação, métricas de reuso, prints, relatório
data/synthetic/    conjunto de dados sintético (seed e avaliação)
docs/
  architecture/    diagramas Mermaid e ADRs
  scrum/           Product Backlog e sprint-0..4
  relatorio/       relatorio.md, imagens, build/ (DOCX e PDF)
  STUDY_GUIDE.md   guia de estudo para a defesa
```

## Documentação

- Relatório final: [`docs/relatorio/build/relatorio.pdf`](docs/relatorio/build/relatorio.pdf)
  (fonte em [`docs/relatorio/relatorio.md`](docs/relatorio/relatorio.md)).
- Guia de estudo: [`docs/STUDY_GUIDE.md`](docs/STUDY_GUIDE.md).
- Decisões de arquitetura: [`docs/architecture/adr/`](docs/architecture/adr/).
- Scrum: [`docs/scrum/`](docs/scrum/); andamento: [`PROGRESS.md`](PROGRESS.md).
- OpenAPI: cada serviço publica `/docs` na rede interna do Compose (porta 8000);
  o gateway expõe <http://localhost:8000/docs> e a tabela de rotas em
  <http://localhost:8000/routes>.
