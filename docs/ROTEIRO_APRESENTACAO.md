# Roteiro de apresentação — EstágioHub

Roteiro exato para a apresentação ao professor: **15 minutos** de
apresentação + perguntas. Para cada bloco: quem fala, o que fica na tela, o que
clicar, o que digitar e a fala.

- **Victor** (Product Owner) — abre, fala de reuso e de recomendação/IA.
- **Lorenzo** (Scrum Master) — fala de metodologia, arquitetura e qualidade, e
  **opera o computador** durante a demonstração.

As páginas citadas são do PDF `docs/relatorio/build/relatorio.pdf`
(71 páginas). As perguntas prováveis e as respostas estão em
[`STUDY_GUIDE.md`](STUDY_GUIDE.md), seção 4.

---

## 0. Preparação (no dia, 15 minutos antes)

1. Partir de um estado limpo, para a demonstração não mostrar dados de testes
   anteriores:

   ```bash
   make clean
   ```
   ```bash
   make up
   ```
   ```bash
   make seed
   ```

2. Abrir **3 janelas anônimas** (cada uma guarda seu próprio login) em
   <http://127.0.0.1:8080> e entrar:

   | Janela | E-mail | Senha |
   |---|---|---|
   | A — Empresa | `rh@techsolucoes.test` | `Empresa@2026` |
   | B — Estudante | `estudante@ufal.test` | `Estudante@2026` |
   | C — Coordenação | `coordenacao@ufal.test` | `Coord@2026` |

3. Na janela C, deixar aberta a aba **Status dos serviços** (menu lateral,
   embaixo). Conferir: "Todos os serviços operacionais".
4. Em outra aba: o PDF do relatório aberto na **página 23**.
5. Deixar um **terminal** aberto na pasta do projeto (para o bloco de
   degradação graciosa).
6. Opcional: painel do RabbitMQ em <http://localhost:15672> (usuário
   `estagiohub`, senha = `RABBITMQ_PASSWORD` do `.env`).

**Dados que serão digitados na demonstração** (deixar à mão):

| Campo | Valor |
|---|---|
| Título da vaga | `Estágio em Integração de Sistemas` |
| Descrição | `Desenvolver integrações entre microsserviços com Python, FastAPI e mensageria.` |
| Requisitos | `Python, FastAPI, Docker, RabbitMQ` |
| Curso / período mínimo | Ciência da Computação / `4` |
| Horas por dia / semana | primeiro `8` (para mostrar o erro), depois `6` / `30` |
| Modalidade / cidade / bolsa | Híbrido / `Maceió` / `1500` |
| Início / término do estágio | daqui a 7 dias / daqui a 1 ano |
| Supervisor(a) | `Carla Mendes` |
| Seguradora / apólice | primeiro **em branco** (para mostrar o erro), depois `Seguradora Exemplo` / `AP-2026-001` |

---

## 1. Abertura — 0:00 a 1:00 · Victor

**Tela:** capa do PDF (página 1).

> "Bom dia, professor. Somos Victor e Lorenzo, e vamos apresentar o
> **EstágioHub**, um sistema de gerenciamento de estágios universitários
> construído com **microsserviços**, **componentes de software** e **agentes de
> IA**.
>
> O problema: o estágio é regido pela Lei 11.788 de 2008, que exige jornada de
> no máximo 6 horas por dia e 30 por semana, no máximo 2 anos na mesma empresa,
> seguro contra acidentes e relatório a cada 6 meses. Hoje isso é controlado por
> e-mail e planilha.
>
> O EstágioHub cobre o ciclo inteiro: a empresa publica a vaga, o estudante
> recebe recomendações explicadas e se candidata, a empresa aprova, o termo de
> compromisso é gerado em PDF, a coordenação aprova, o estágio fica ativo e todos
> são notificados — com as regras da lei validadas automaticamente."

---

## 2. Metodologia — 1:00 a 2:30 · Lorenzo

**Tela:** PDF, **página 18** (Tabela 12 — Product Backlog).

> "Usamos **Scrum**. O Victor foi o Product Owner, eu fui o Scrum Master, e nós
> dois formamos o time de desenvolvimento.
>
> Como o trabalho foi intensivo, fizemos **cinco micro-sprints de cerca de duas
> horas**: fundação; identidade e vagas; candidaturas e documentos;
> inteligência; e qualidade e entrega. Cada sprint teve meta, histórias
> selecionadas do backlog, tarefas estimadas e uma *review* com evidências — e
> terminou com uma **tag no Git**, de `sprint-0` a `sprint-4`.
>
> O Product Backlog tem 31 histórias no formato 'Como… quero… para…', com
> prioridade MoSCoW, *story points* em Fibonacci e critérios de aceitação
> Dado/Quando/Então. Nossa Definition of Done: código documentado, testes
> passando, lint sem erros, serviço saudável no Docker e documentação
> atualizada.
>
> Em cada sprint registramos os **problemas reais** que apareceram e como
> resolvemos — por exemplo, um erro do SQLAlchemy assíncrono que corrigimos uma
> única vez no componente de banco e todos os serviços se beneficiaram."

---

## 3. Técnicas de reuso — 2:30 a 4:30 · Victor

**Tela:** PDF, **página 12** (Tabela 7 — matriz de reuso) → **página 14**
(Figura 1) → **página 15** (Tabela 8 — métricas).

> "O trabalho pede duas técnicas de reuso.
>
> A primeira são os **microsserviços**: o sistema tem 8 serviços — gateway,
> usuários, vagas, candidaturas, documentos, notificações, recomendação e
> agentes —, cada um com o **seu próprio banco de dados**. Um serviço nunca
> acessa o banco do outro.
>
> A segunda são os **componentes de software**. Criamos 6 pacotes Python
> instaláveis — autenticação, eventos, banco, observabilidade, cliente HTTP
> resiliente e interface —, cada um com **versão semântica**, interface pública
> explícita, interface requerida documentada e testes com **100% de cobertura**.
>
> *(mostrar a Tabela 7)* Esta matriz mostra qual serviço reutiliza qual
> componente — calculada automaticamente a partir dos imports do código.
>
> *(mostrar a Tabela 8)* E aqui está o resultado: cerca de **53% do código** que
> cada serviço executa vem dos componentes. Sem eles, teríamos copiado cerca de
> **7 mil linhas** entre os serviços."

---

## 4. Arquitetura — 4:30 a 6:00 · Lorenzo

**Tela:** PDF, **página 23** (Figuras 2 e 3) → **página 24** (Figura 4).

> "*(Figura 2)* O usuário só fala com o frontend, e o frontend só fala com o
> **API Gateway**, que escrevemos em Python. O gateway valida o token JWT e o
> papel do usuário, roteia para o serviço certo e tem *timeout*, *retry* e
> *circuit breaker* para cada serviço.
>
> *(Figura 3)* Para o que muda o estado de outro serviço usamos **eventos no
> RabbitMQ**: são 10 tipos de evento num *topic exchange*. Cada consumidor
> descarta mensagens repetidas pelo identificador do evento e tem uma *dead
> letter queue* para as que falham.
>
> *(Figura 4)* O fluxo principal é uma **saga coreografada**: quando a empresa
> aprova, o serviço de candidaturas publica um evento; o serviço de documentos
> gera o termo em PDF e publica outro evento; a candidatura vai para 'TCE
> pendente'; a coordenação aprova; e o estágio fica ativo. Não há orquestrador
> central — cada serviço reage aos eventos. Vamos ver isso funcionando."

---

## 5. Demonstração ao vivo — 6:00 a 12:00 · Lorenzo opera, cada um narra sua parte

### 5.1 Status — 6:00 a 6:30 (Lorenzo)

**Janela C**, aba **Status dos serviços**.

> "Esta tela consulta todos os serviços pelo gateway a cada 5 segundos: status,
> versão, latência, banco e tempo no ar. Estão todos operacionais."

### 5.2 Empresa publica a vaga — 6:30 a 7:30 (Victor narra)

**Janela A** (empresa).

1. Ligar o *toggle* **Mostrar microsserviços** (canto superior direito).
   > "Com isto ligado, cada painel fica com a cor do microsserviço que forneceu
   > os dados — a informação vem de um *header* que cada serviço devolve."
2. Menu lateral → **Publicar vaga**. Preencher com os dados da tabela de
   preparação, **com 8 em "Horas por dia"** → **Publicar vaga**.
   > "Vou tentar uma jornada de 8 horas por dia… o backend recusa: a lei
   > limita a 6."
3. Trocar para **6** e **30** → **Publicar vaga**.
   > "Agora a vaga foi publicada, e o serviço de vagas publicou um evento
   > avisando o resto do sistema."

### 5.3 Estudante: recomendação e assistente — 7:30 a 9:00 (Victor narra)

**Janela B** (estudante).

1. Menu lateral → **Recomendações**. Localizar **Estágio em Integração de
   Sistemas** (deve estar entre as primeiras).
   > "A vaga que acabou de ser publicada já aparece recomendada, com a
   > explicação: a estudante tem 3 das 4 habilidades — Python, FastAPI e Docker
   > — e falta RabbitMQ. A recomendação não usa IA: é um algoritmo
   > determinístico e explicável."
2. Clicar **Perguntar ao assistente IA** → **Executar agente**.
   > "O assistente de IA explica por que a vaga combina, sugere melhorias no
   > perfil e escreve um rascunho de carta que a estudante pode editar. Embaixo
   > está a **trilha de execução**: cada ferramenta que o agente chamou fica
   > registrada. Sem chave da API, ele roda em modo regras com a mesma
   > interface."
3. Voltar em **Recomendações** → **Ver e candidatar-se** na vaga → escrever
   uma frase na **Carta de motivação** → **Candidatar-me**.

### 5.4 Empresa: ranking e aprovação — 9:00 a 10:15 (Lorenzo narra)

**Janela A** (empresa).

1. Menu lateral → **Minhas vagas** → abrir a vaga → **Ver candidatos**.
   > "A empresa vê o ranking de candidatos, calculado pelo mesmo algoritmo de
   > recomendação, com a justificativa de cada um."
2. Clicar no nome da candidata → **Iniciar análise** → **Aprovar e informar
   termos**.
3. Preencher início, término e supervisor, **deixando seguradora e apólice em
   branco** → **Aprovar candidato**.
   > "Sem seguro contra acidentes, a lei não permite o termo — e o sistema
   > recusa."
4. Preencher **Seguradora Exemplo** / **AP-2026-001** → **Aprovar candidato**.
   > "Aprovado. A partir daqui começa a saga: o serviço de documentos vai gerar
   > o PDF sozinho."

### 5.5 Coordenação aprova o TCE — 10:15 a 11:00 (Lorenzo narra)

**Janela C** (coordenação).

1. Menu lateral → **Painel** → no quadro **TCE aguardando aprovação**, clicar
   **Revisar** na linha da Ana Beatriz Souza.
   > "Esta é a pré-visualização do termo de compromisso gerado em PDF, com as
   > cláusulas da lei: jornada, vigência, bolsa, seguro e supervisão."
2. Clicar **Aprovar TCE**.
   > "A coordenação aprovou; o serviço de documentos publica o evento e o
   > serviço de candidaturas ativa o estágio."

### 5.6 Estudante: estágio ativo e notificações — 11:00 a 11:30 (Victor narra)

**Janela B** (estudante).

1. Menu lateral → **Candidaturas** → abrir o cartão em **Estágio ativo**.
   > "No histórico aparecem as transições feitas pelas pessoas e as feitas
   > pelo sistema, a partir dos eventos. Uma transição fora da ordem — por
   > exemplo, desistir de um estágio ativo — é recusada com erro 409."
2. Menu lateral → **Notificações**.
   > "Cada etapa gerou notificações para os envolvidos, a partir dos eventos."

### 5.7 Degradação graciosa — 11:30 a 12:00 (Lorenzo)

No **terminal**:

```bash
docker compose stop recommendation-service
```

Na **janela B**, recarregar o **Painel**.

> "Derrubei o serviço de recomendação. O painel avisa que ele está fora, mas o
> resto do sistema continua funcionando."

No **terminal**:

```bash
docker compose start recommendation-service
```

---

## 6. Recomendação e IA — 12:00 a 13:30 · Victor

**Tela:** PDF, **página 38** (Figura 6) → **página 39** (Tabela 24).

> "O recomendador é **híbrido**: primeiro aplica filtros duros — curso,
> período, carga horária e as regras da lei —; depois calcula a similaridade
> TF-IDF com cosseno entre o perfil e a vaga, o índice de Jaccard entre as
> habilidades e um bônus de preferência. O score final pondera os três: 50%,
> 35% e 15%. Sem perfil preenchido, ele usa recência e popularidade.
>
> *(Tabela 24)* Avaliamos offline com um conjunto **sintético**, declarado no
> relatório. O híbrido teve **nDCG@5 de 0,965**, contra 0,825 do baseline só
> com filtros e 0,151 do aleatório.
>
> Os **agentes de IA** usam a API do Claude com chamada de ferramentas, no
> máximo 6 passos por execução. Eles só leem, sugerem e notificam: **nenhum
> agente consegue aprovar ou rejeitar uma candidatura** — a decisão é sempre
> humana."

---

## 7. Qualidade e encerramento — 13:30 a 15:00 · Lorenzo

**Tela:** PDF, **página 15** (Tabela 9 — testes) → **página 70** (checklist).

> "Sobre qualidade: temos **295 testes automatizados**, os componentes com 100%
> de cobertura, um **teste de ponta a ponta** que executa o fluxo que acabamos
> de mostrar, integração contínua no GitHub Actions e **11 registros de decisão
> de arquitetura**. Todos os prints do relatório foram gerados automaticamente
> executando o sistema pela própria interface.
>
> Limitações que conhecemos: a publicação de eventos não usa o padrão
> *outbox*, e a avaliação da recomendação usa dados sintéticos.
>
> *(checklist)* O relatório segue a numeração do modelo e termina com este
> checklist, que liga cada item do modelo à seção e à evidência.
>
> Tudo está no repositório do GitHub e sobe com três comandos. Obrigado —
> ficamos à disposição para perguntas."

---

## 8. Plano B

| Problema | O que fazer |
|---|---|
| A interface travou ou um passo falhou | No terminal, rodar `make e2e`: executa o mesmo fluxo pela API e imprime as 9 etapas. |
| A vaga nova não aparece nas recomendações | Recarregar a página após 2–3 segundos (os eventos são assíncronos). |
| Sem internet | Nada muda: os agentes rodam em modo regras e não há recursos externos. |
| Tempo curto | Pular os blocos 5.3 (assistente) e 5.7 (degradação) e mostrar as Figuras 14 e 30 do PDF (seção 8). |
| `localhost:8080` abre outra aplicação | Usar <http://127.0.0.1:8080>. |
