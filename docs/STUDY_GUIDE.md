# Guia de estudo para a defesa — EstágioHub

Material de preparação da equipe para a apresentação e a arguição. Cada
resposta aponta para o arquivo ou a seção do relatório onde está a evidência.

---

## 1. O sistema em uma página

**O que é.** Um sistema web que gerencia o estágio universitário do começo ao
fim, seguindo a Lei nº 11.788/2008: a empresa publica a vaga, o estudante recebe
recomendações explicadas e se candidata, a empresa aprova informando os termos,
o Termo de Compromisso (TCE) é gerado em PDF, a coordenação aprova, o estágio
fica ativo, o estudante envia relatórios e todos são notificados.

**Técnicas de reuso exigidas.**
- **Microservices:** 8 serviços + frontend, cada um com seu banco
  (*Database per Service*), comunicando-se por REST (síncrono) e por eventos no
  RabbitMQ (assíncrono).
- **Componentes de Software:** 6 pacotes Python instaláveis em `components/`
  (`eh_auth`, `eh_events`, `eh_db`, `eh_observability`, `eh_http`, `eh_ui`),
  com versão semântica, interface pública explícita, README e testes (≥ 80%).
- **Agentes de IA (opcional):** 3 agentes com Claude (*tool use*) e fallback
  determinístico.

**Números para ter de cabeça** (confira os valores atuais no relatório,
seções 4.4, 4.5 e 6.4):

| Item | Valor |
|---|---|
| Containers no Compose | 17 (8 serviços, frontend, 5 PostgreSQL, MongoDB, Redis, RabbitMQ) |
| Eventos | 10 tipos no *topic exchange* `estagiohub.events` |
| Componentes | 6 pacotes, cobertura de 100% |
| Reuso | ~53% do código executado por serviço vem dos componentes (`make eval`) |
| Testes | ~290 testes automatizados + e2e de 9 etapas |
| Recomendador | nDCG@5 ≈ 0,97 (híbrido) × 0,83 (só filtros) × 0,15 (aleatório), dados sintéticos |
| Sprints | 5 micro-sprints de ~2 h, tags `sprint-0` a `sprint-4` |

**Mapa dos serviços.**

| Serviço | Faz | Banco | Publica | Consome |
|---|---|---|---|---|
| api-gateway | entrada única, JWT/papéis, resiliência, `/services` | — | — | — |
| user-service | contas, login (JWT), perfis | PostgreSQL | `user.registered`, `profile.updated` | — |
| internship-service | vagas (jornada legal validada) | PostgreSQL | `internship.published`, `internship.closed` | — |
| application-service | candidaturas, máquina de estados, regras da lei | PostgreSQL | `application.submitted`, `application.status_changed` | `agreement.*`, `report.submitted` |
| document-service | TCE em PDF, aprovação, relatórios com versões | MongoDB + volume | `agreement.generated`, `agreement.approved`, `report.submitted` | `application.status_changed` |
| notification-service | caixas de notificação | Redis | — | todos (`#`) |
| recommendation-service | recomendação e ranking | PostgreSQL (read model) | — | usuários, vagas, candidaturas |
| agent-service | agentes de IA | PostgreSQL | `report.due_soon` | — |
| web-frontend | interface (Jinja2 + HTMX) | — | — | — |

---

## 2. O caminho de uma requisição

Exemplo: a empresa aprova um candidato.

1. **Navegador → web-frontend** (`POST /candidaturas/7/aprovar`). O frontend lê
   o JWT do *cookie* HttpOnly e monta o corpo com os termos.
2. **web-frontend → api-gateway** (`POST /api/applications/7/approve`) via
   `GatewayClient` (`eh_http.ResilientClient`), com `X-Correlation-ID`.
3. **api-gateway**: `ObservabilityMiddleware` fixa o *correlation-id*;
   `resolve_route` escolhe `application-service`; `authenticate` valida o JWT;
   `authorise` aplica a política (só `company`); `forward` encaminha com
   *timeout*, *retry* e *circuit breaker* (`api_gateway/proxy.py`).
4. **application-service**: `require_role(COMPANY)` revalida o token (defesa em
   profundidade); carrega a candidatura do **próprio banco**; aplica
   `validate_workload`, `validate_insurance` e `validate_duration`
   (`domain.py`); chama `transition` (409 se inválida); faz `commit` e só então
   publica `application.status_changed` com os termos (`eh_events`).
5. **Resposta** volta com `X-Served-By: application-service`; o gateway preserva
   o header; o frontend mostra o *badge* do serviço no painel.
6. **Depois, de forma assíncrona (saga):** `document-service` gera o PDF e
   publica `agreement.generated` → `application-service` muda para
   `agreement_pending` → `notification-service` avisa estudante, empresa e
   coordenação. Cada consumidor deduplica por `event_id`; falhas viram *retry*
   e, esgotadas, DLQ.

Para rastrear tudo: o mesmo *correlation-id* aparece nos logs JSON do frontend,
do gateway e do serviço (`docker compose logs`).

---

## 3. Decisões e *trade-offs*

| Decisão | Por quê | Custo aceito |
|---|---|---|
| Microsserviços por subdomínio (ADR-001) | Exigência do trabalho; contextos com dados e ciclos diferentes (documentos binários, notificações voláteis, modelo de leitura) | Mais containers, consistência eventual |
| Database per Service | Isolamento de dados e de falhas; banco adequado a cada contexto | Sem *joins* entre serviços; dados copiados por eventos |
| Gateway próprio em Python (ADR-003) | O relatório exige código documentado do gateway | Menos desempenho que um proxy nativo |
| Saga coreografada (ADR-004) | Fluxo curto (2 serviços); baixo acoplamento | Fluxo espalhado no código → mitigado com diagrama e *correlation-id* |
| Publicar após o `commit` | Simples e nunca anuncia algo que não foi gravado | Se o processo cair entre `commit` e publicação, o evento se perde → solução completa seria *transactional outbox* |
| Event-carried state transfer | Consumidores não precisam chamar o produtor (desacopla e evita cascata de falhas) | *Payloads* maiores, versionamento de contrato |
| Componentes sem dependência entre si (ADR-005) | Interfaces requeridas explícitas; troca de implementação (ex.: idempotência SQL/Redis/Mongo) | Um pouco mais de "cola" nos serviços |
| Mesma *stack* em todos (ADR-002) | Equipe pequena; reuso por componentes só é possível com a mesma linguagem | Não explora heterogeneidade tecnológica |
| SSR com HTMX (ADR-007) | Sem *build* JS, token fora do alcance de JavaScript, funciona offline | Interatividade limitada |
| Recomendador sem LLM (ADR-010) | Determinístico, explicável, avaliável, sem custo nem rede | TF-IDF não entende sinônimos |
| Agentes com fallback (ADR-011) | Demonstração funciona sem chave; decisões continuam humanas | Respostas por *template* no modo regras |

---

## 4. Perguntas prováveis do professor — e respostas

### Metodologia e processo

**1. Por que Scrum e não um processo dirigido a planos?**
O escopo era grande e o prazo curto; precisávamos de incrementos integrados e
verificáveis a cada iteração e de priorização por valor (MoSCoW). O Scrum deu
isso: cinco micro-sprints, cada uma com meta, histórias, tarefas estimadas,
Definition of Done e *review* com evidências (tag Git, resultado de `make test`).
Também nos permitiu adaptar o plano quando surgiram problemas reais (ex.: o
`MissingGreenlet` corrigido no componente `eh_db` na Sprint 1).
→ Relatório, seção 2; `docs/scrum/`.

**2. Como uma sprint de 2 horas é Scrum de verdade?**
O que caracteriza o Scrum são os eventos, papéis e artefatos com *timebox*, não
a duração. Cada micro-sprint teve *planning* (histórias + tarefas), execução,
*review* com incremento potencialmente entregável (stack *healthy* + testes) e
registro de retrospectiva. A duração curta foi uma escolha do formato
intensivo do trabalho.

**3. Quem decide prioridade? Como os story points foram estimados?**
O Product Owner (Victor) prioriza o backlog por MoSCoW; o time estima em
Fibonacci pela complexidade relativa (ex.: geração do TCE = 8 por envolver PDF,
saga e regra legal; encerrar vaga = 1). → `docs/scrum/product-backlog.md`.

**4. Qual foi a Definition of Done?**
Código com *docstrings* (verificado pelo `ruff`, regras D100/D101/D103),
testes passando, `ruff` sem erros, serviço *healthy* no Compose e documentação
atualizada.

### Técnicas de reuso

**5. Qual a diferença entre um componente e uma biblioteca comum?**
Pela definição de Szyperski, componente é uma unidade de composição com
interface especificada e dependências de contexto explícitas, implantável de
forma independente. Nossos componentes têm: interface pública declarada
(`__all__`), interface requerida documentada no README, versão semântica,
testes próprios e são instalados por caminho no Dockerfile — o serviço só
conhece a interface. Exemplo de dependência explícita: o `EventConsumer` exige
um `IdempotencyStore` (protocolo), e cada serviço injeta a sua implementação
(SQL no `eh_db`, Redis no `notification-service`, Mongo no `document-service`).

**6. Onde está o reuso entre microsserviços, e não só dentro deles?**
Em dois níveis: (a) componentes reutilizados por vários serviços (matriz de
reuso, Tabela 7); (b) serviços reutilizados como capacidade por vários
consumidores — o `recommendation-service` serve o frontend e os agentes; o
`notification-service` atende eventos de todos; o gateway é reutilizado por
qualquer cliente.

**7. Como vocês mediram o reuso?**
`scripts/reuse_metrics.py` conta linhas lógicas (sem comentários e
*docstrings*) de cada serviço e dos componentes que ele importa (análise
estática com `ast`). Resultado: cerca de metade do código que cada serviço
executa vem de componentes, e milhares de linhas deixaram de ser duplicadas.
→ Tabela 8.

**8. Componentes compartilhados não criam acoplamento entre microsserviços?**
Criam um acoplamento **de código**, não **de execução**: cada serviço embute
sua cópia na imagem e pode ficar numa versão diferente. A versão semântica
sinaliza mudanças incompatíveis; por isso o `eh_events` foi de 0.1 para 0.2
apenas com campos **opcionais** (compatível). O que não compartilhamos são
modelos de domínio nem bancos.

### Arquitetura de microsserviços

**9. Por que esses 8 serviços e não mais ou menos?**
Decomposição por subdomínio: identidade, vagas, candidaturas/estágio (regras
legais), documentos (binários), notificações (alto volume, voláteis),
recomendação (modelo de leitura) e agentes (histórico de execuções). Cada um
tem dados e motivo de mudança próprios. Juntar candidaturas e documentos, por
exemplo, misturaria PostgreSQL transacional com arquivos e MongoDB.

**10. Como garantem que um serviço não acessa o banco de outro?**
Cada banco é um container separado com credenciais e rede; cada serviço só
recebe a `DATABASE_URL` do seu banco (`docker-compose.yml`). Dados de outros
contextos chegam por REST ou por eventos (ex.: o modelo de leitura da
recomendação).

**11. Quando vocês usam REST e quando usam eventos?**
REST para **consultas** necessárias para responder agora (ex.: ao receber uma
candidatura, o `application-service` consulta a vaga e o perfil). Eventos para
**propagar mudanças de estado** a quem se interessar (notificações, modelo de
leitura, saga). Assim o produtor não depende da disponibilidade dos
consumidores.

**12. O que acontece se o RabbitMQ cair?**
Os serviços ficam `not_ready` (o `/ready` verifica o *broker*) e a tela de
status mostra isso. As conexões são *robust* (reconectam). Mensagens já
publicadas estão em filas duráveis com entrega persistente; quando o
consumidor volta, processa o que ficou na fila. Limitação: a publicação ocorre
após o `commit`, então um evento pode se perder se o processo morrer entre os
dois passos — a evolução seria o padrão *outbox*.

**13. Explique a saga. Por que coreografada?**
A saga é a sequência aprovação → TCE → aprovação da coordenação → estágio
ativo, que atravessa dois bancos diferentes (PostgreSQL e MongoDB) — não dá
para usar uma transação ACID. Cada serviço faz sua parte localmente e publica
um evento que dispara o próximo passo (Figura 4). Escolhemos coreografia porque
o fluxo é curto, envolve poucos serviços e evita um orquestrador central; se o
fluxo crescesse, um orquestrador facilitaria a visibilidade.

**14. E as compensações da saga?**
Os passos são protegidos antes de começar: a aprovação já valida seguro,
jornada e duração (422 se faltar algo). Se mesmo assim o `document-service`
não puder gerar o TCE (sem seguro), ele não emite o documento e a candidatura
fica em `approved` — visível na interface. Eventos repetidos ou atrasados são
ignorados porque a máquina de estados rejeita transições inválidas e os
consumidores deduplicam por `event_id`.

**15. Como funciona a idempotência e a DLQ?**
O `EventConsumer` (`eh_events/consumer.py`) verifica `seen(event_id)` antes de
processar e `mark` depois; duplicatas recebem `ack` sem efeito. Se o
*handler* falha, a mensagem é republicada com o header `x-retry` e *backoff*
exponencial; após `max_retries`, é rejeitada sem *requeue* e o RabbitMQ a envia
para `<fila>.dlq` pelo *dead-letter exchange*. Mensagens inválidas vão direto
para a DLQ.

**16. O que é o *circuit breaker* e onde ele aparece?**
Em `eh_http.CircuitBreaker`: depois de N falhas consecutivas o circuito
**abre** e as chamadas falham imediatamente (sem esperar *timeout*), por um
tempo; depois fica **meio-aberto** e uma chamada de teste decide se fecha. O
gateway tem um por upstream; quando abre, devolve 503 com
`reason: circuit_open` e o frontend mostra o aviso de degradação.

**17. Por que o *retry* não repete POST?**
POST não é idempotente: repetir pode aplicar a operação duas vezes (duas
candidaturas). O `ResilientClient` só repete POST quando a conexão nem chegou
a ser estabelecida (`ConnectError`), ou seja, quando temos certeza de que nada
foi enviado.

**18. O que é o modelo de leitura (CQRS leve)?**
O `recommendation-service` não consulta os bancos de usuários e vagas; ele
mantém tabelas próprias (`rm_students`, `rm_internships`, `rm_applications`)
atualizadas por eventos — o lado de **leitura** separado do lado de
**escrita**. Se o modelo se perder, `POST /recommendations/rebuild` o
reconstrói via REST. Foi o que fizemos quando o serviço entrou depois de já
existirem dados (problema real da Sprint 3).

**19. Como o gateway sabe se cada serviço está saudável?**
Todo serviço expõe `/health` (*liveness*), `/ready` (verifica banco e
*broker*) e `/version` (componente `eh_observability`). O
`GET /services` do gateway chama `/ready` e `/version` de todos em paralelo e
classifica `up`/`degraded`/`down`, com latência e *uptime*. O Compose usa
`/ready` no `healthcheck` e `depends_on: service_healthy`.

**20. Como a interface mostra quais serviços forneceram os dados?**
Cada serviço responde com `X-Served-By` (middleware do `eh_observability`); o
gateway preserva o header; o `GatewayClient` do frontend devolve
`ApiResult.served_by`; a macro `ui.card(service=...)` do `eh_ui` exibe o
*badge* e marca o painel com `data-service`. O *toggle* "Mostrar microsserviços"
liga uma classe CSS que contorna cada painel com a cor do serviço.

### Segurança

**21. Como funciona a autenticação?**
O `user-service` verifica a senha com argon2id e emite um JWT HS256 com `sub`,
`role`, `name`, `exp` e `iss`. O gateway valida o token e a política de papéis
na borda; cada serviço valida de novo com `require_role` (defesa em
profundidade). O frontend guarda o token em *cookie* HttpOnly + SameSite=Lax,
fora do alcance de JavaScript.

**22. Um estudante consegue ver o perfil ou a candidatura de outro?**
Não. O `user-service` só deixa estudante ler o próprio perfil; o
`application-service` filtra por `student_id`/`company_id` (`scope_filter`) e
devolve 403 a quem não é dono; o `document-service` faz o mesmo nos TCEs e
relatórios. Há testes para cada caso.

**23. E os segredos?**
Nada real é versionado: `.env` está no `.gitignore`; `make env` gera
`JWT_SECRET` e senhas aleatórias a partir do `.env.example` vazio. Containers
rodam como usuário não-root; CORS só aceita a origem do frontend.

### Regras de negócio

**24. Quais regras da Lei 11.788 o sistema valida e onde?**
Jornada ≤ 6 h/dia e 30 h/semana (vaga e aprovação; também *check constraint*
no banco); duração ≤ 2 anos **cumulativos** na mesma concedente, exceto PcD;
seguro contra acidentes pessoais para emitir o TCE (validado na aprovação e de
novo na geração do PDF); relatório no máximo a cada 6 meses (prazo calculado a
partir do início do estágio e renovado a cada relatório). Tudo em funções puras
em `application_service/domain.py`, com testes de borda (ex.: 2 anos
terminando em 30/11/2028 para início em 01/12/2026).

**25. Por que uma transição inválida retorna 409?**
409 *Conflict* indica que a requisição é válida mas conflita com o **estado
atual** do recurso — exatamente o caso de tentar, por exemplo, desistir de um
estágio ativo. Erros de regra legal são 422 (dados inválidos para a regra).
Testamos todas as 81 combinações de estados.

### Recomendação

**26. Como o recomendador funciona?**
Filtros duros (curso, período, disponibilidade, vaga aberta, jornada legal) →
TF-IDF + cosseno entre perfil e vaga → Jaccard entre habilidades → bônus de
preferência → `score = 0,50·cos + 0,35·Jaccard + 0,15·pref`. Cada resultado
traz habilidades em comum, faltantes e o motivo de eliminação. Sem perfil,
usa recência e popularidade (*cold start*). → Seção 6.4.

**27. Por que híbrido e não só um dos métodos?**
O TF-IDF capta o texto (resumo, descrição); o Jaccard dá uma explicação
simples ("você tem 3 de 4 habilidades"); as preferências personalizam. A
combinação equilibra relevância e explicabilidade. Na avaliação, a ablação
"só conteúdo" ficou ligeiramente acima no nDCG; mantivemos os pesos sem
ajustar ao conjunto sintético para não sobreajustar.

**28. Os dados da avaliação são reais?**
Não, e isso está declarado: o conjunto é **sintético** (Faker pt_BR, semente
fixa), gerado pelo mesmo script do seed. Os rótulos vêm de uma "trilha de
interesse" escondida, e não das habilidades que o algoritmo vê, para não ser
circular; mesmo assim o conjunto favorece métodos de conteúdo. Medimos
precision@5 e nDCG@5 contra *baselines* aleatório e só-filtros.

**29. Por que a precision@5 do híbrido é parecida com a do só-filtros?**
Porque cada estudante tem poucas vagas elegíveis no seu curso; os dois métodos
acabam devolvendo quase o mesmo conjunto. A diferença está na **ordem** — o
nDCG@5 do híbrido é bem maior, ou seja, ele coloca a vaga certa no topo.

**30. Por que não usar um LLM para recomendar?**
Recomendação precisa ser determinística, explicável, avaliável e barata. O
LLM entra apenas nos agentes, que **explicam** a saída do recomendador em vez
de decidir.

### Agentes de IA

**31. O que os agentes podem e não podem fazer?**
Podem ler (perfil, vagas, recomendações, ranking, estágios, relatórios),
sugerir e notificar. Não existe ferramenta nem cliente HTTP capaz de mudar o
status de uma candidatura — a decisão é sempre humana. Cada agente só vê sua
lista de ferramentas; o estudante só consulta os próprios dados. Há teste que
verifica isso.

**32. E se não houver chave da API ou o modelo falhar?**
Sem `ANTHROPIC_API_KEY`, o serviço roda em **modo regras**: um plano fixo chama
as mesmas ferramentas e monta a resposta por *templates* — mesma API, selo "IA
em modo regras" na interface. Com chave, se o modelo recusar, estourar 6
passos ou o *timeout*, o serviço cai automaticamente para o modo regras e
registra o motivo.

**33. Como vocês testam um agente sem chamar a API?**
O cliente LLM é sempre substituído por um dublê programável nos testes
(`ScriptedLlm`), que devolve respostas com `tool_use` e `end_turn`.
Verificamos o laço, a trilha, o limite de passos, a recusa e o *timeout*.

**34. O que é a "trilha de execução"?**
Cada chamada ao modelo e a ferramentas é gravada (`agent_runs`,
`agent_steps`) com entrada, saída, duração e sucesso, e aparece na interface.
Serve de auditoria: dá para ver exatamente o que o agente consultou.

### Qualidade e operação

**35. Qual a estratégia de testes?**
Pirâmide: testes unitários de domínio (máquina de estados, regras legais,
recomendador), testes de API de cada serviço com SQLite em memória e dublês
(`InMemoryPublisher`, `httpx.MockTransport`, fakeredis), testes dos
componentes (cobertura 100%), e o e2e (`make e2e`) do fluxo completo via
gateway contra a stack real. Os prints (`make screenshots`) também percorrem o
fluxo pela interface.

**36. Que problemas reais vocês enfrentaram?**
Exemplos: `MissingGreenlet` ao ler `updated_at` no SQLAlchemy assíncrono
(corrigido no `eh_db` com `eager_defaults`); cobertura subestimada por
*greenlets*; *headers* duplicados no proxy por diferença de maiúsculas; porta
8080 ocupada em IPv6 por um processo do WSL; modelo de leitura vazio para dados
antigos (resolvido com `rebuild`); prazo do relatório contado a partir da data
errada; imagem do Playwright sem o pacote Python. Todos estão em
`docs/scrum/sprint-N.md`.

**37. Como o sistema escalaria?**
Serviços *stateless* podem ter várias réplicas atrás do gateway; os
consumidores de uma mesma fila competem pelas mensagens (é preciso então
garantir ordem por agregado ou aumentar a idempotência); os bancos escalam
independentemente. O gargalo provável seria o modelo de leitura de
recomendação, que poderia ganhar índice vetorial.

**38. Quais as limitações e próximos passos?**
*Outbox* para não perder eventos entre `commit` e publicação; assinatura
digital do TCE; *embeddings* no recomendador; *object storage* no lugar do
volume; observabilidade distribuída (OpenTelemetry); testes de contrato entre
serviços.

---

## 5. Roteiro de demonstração (5 minutos)

> Versão resumida. O roteiro completo da apresentação (15 minutos, com falas,
> cliques, dados a digitar e páginas do PDF) está em
> [`ROTEIRO_APRESENTACAO.md`](ROTEIRO_APRESENTACAO.md).

Antes: `make env && make up && make seed` (já com tudo *healthy*). Abrir
<http://localhost:8080> (ou <http://127.0.0.1:8080>) em uma janela e o painel
do RabbitMQ em outra aba.

| Tempo | Ação | O que dizer |
|---|---|---|
| 0:00–0:30 | Tela **Status dos serviços** (`/status`) | "17 containers; cada serviço tem seu banco; o gateway agrega `/ready` e `/version`." |
| 0:30–1:15 | Login como **empresa** (`rh@techsolucoes.test` / `Empresa@2026`); ligar **Mostrar microsserviços**; publicar uma vaga | "Cada painel tem a cor do serviço que forneceu os dados; a jornada é validada no backend." |
| 1:15–2:00 | Login como **estudante** (`estudante@ufal.test` / `Estudante@2026`); **Recomendações** | "Híbrido e explicável: habilidades em comum, faltantes, filtros." Abrir o **Assistente IA** e mostrar a trilha. |
| 2:00–2:30 | Candidatar-se à vaga | "Publica `application.submitted`; a empresa é notificada." |
| 2:30–3:15 | Empresa: **Candidatos** (ranking) → **Analisar** → **Aprovar** com seguro | "Regras da lei validadas; a aprovação dispara a saga." |
| 3:15–4:00 | Login como **coordenação** (`coordenacao@ufal.test` / `Coord@2026`); abrir o **TCE** (pré-visualização) → **Aprovar** | "O PDF foi gerado pelo document-service ao consumir o evento; agora `agreement.approved` ativa o estágio." |
| 4:00–4:30 | Estudante: candidatura **ativa** com histórico; **Notificações** | "Transições do sistema aparecem como 'sistema (evento)'." |
| 4:30–5:00 | `docker compose stop recommendation-service`; recarregar o dashboard; depois `docker compose start recommendation-service` | "Degradação graciosa: só o painel de recomendações avisa; o resto funciona." |

Plano B (sem rede/IA): os agentes rodam em modo regras automaticamente. Se a
interface falhar, rodar `make e2e`, que executa o mesmo fluxo pela API e mostra
cada etapa.
