# Product Backlog — EstágioHub

- **Product Owner:** Victor Moura Amaral de Oliveira
- **Scrum Master:** Lorenzo Holanda
- **Time de desenvolvimento:** todos

Priorização MoSCoW (**M**ust, **S**hould, **C**ould, **W**on't) e estimativa em
*story points* na escala de Fibonacci. A coluna *Sprint* indica em qual sprint a
história foi concluída (ver `docs/scrum/sprint-N.md` e as tags `sprint-N`).

## Resumo

| ID | Épico | História (resumo) | MoSCoW | SP | Sprint |
|---|---|---|---|---|---|
| US-01 | E1 Fundação | Subir todo o sistema com um comando | Must | 5 | 0 |
| US-02 | E1 Fundação | Componentes reutilizáveis instaláveis | Must | 8 | 0 |
| US-03 | E1 Fundação | API Gateway com JWT e roteamento | Must | 8 | 0 |
| US-04 | E1 Fundação | CI com lint, testes e build | Should | 3 | 0 |
| US-05 | E1 Fundação | Health checks em todos os serviços | Must | 3 | 0 |
| US-06 | E2 Identidade | Cadastro e login com papéis | Must | 5 | 1 |
| US-07 | E2 Identidade | Perfil acadêmico do estudante | Must | 3 | 1 |
| US-08 | E2 Identidade | Perfil da empresa concedente | Should | 2 | 1 |
| US-09 | E3 Vagas | Publicar vaga com requisitos legais | Must | 5 | 1 |
| US-10 | E3 Vagas | Buscar e filtrar vagas | Must | 3 | 1 |
| US-11 | E3 Vagas | Encerrar vaga | Should | 1 | 1 |
| US-12 | E4 Candidaturas | Candidatar-se a uma vaga | Must | 3 | 2 |
| US-13 | E4 Candidaturas | Analisar, aprovar ou rejeitar candidaturas | Must | 5 | 2 |
| US-14 | E4 Candidaturas | Validar regras da Lei nº 11.788/2008 | Must | 5 | 2 |
| US-15 | E4 Candidaturas | Kanban de candidaturas por status | Should | 3 | 2 |
| US-16 | E5 Documentos | TCE gerado automaticamente em PDF | Must | 8 | 2 |
| US-17 | E5 Documentos | Coordenação aprova o TCE e ativa o estágio | Must | 3 | 2 |
| US-18 | E5 Documentos | Relatórios de atividades com versões | Must | 5 | 2 |
| US-19 | E6 Notificações | Notificação a cada transição | Must | 5 | 2 |
| US-20 | E7 Inteligência | Vagas recomendadas com explicação | Must | 8 | 3 |
| US-21 | E7 Inteligência | Ranking de candidatos para a empresa | Must | 5 | 3 |
| US-22 | E7 Inteligência | Avaliação offline do recomendador | Should | 3 | 3 |
| US-23 | E7 Inteligência | Assistente de Candidatura (IA) | Could | 5 | 3 |
| US-24 | E7 Inteligência | Agente de Acompanhamento de prazos | Should | 5 | 3 |
| US-25 | E7 Inteligência | Agente de Triagem de candidatos | Could | 3 | 3 |
| US-26 | E8 Entrega | Tela de status dos microsserviços | Must | 3 | 4 |
| US-27 | E8 Entrega | Destaque dos microsserviços na interface | Must | 3 | 4 |
| US-28 | E8 Entrega | Teste e2e do fluxo principal | Must | 5 | 4 |
| US-29 | E8 Entrega | Relatório gerado em DOCX e PDF com prints | Must | 5 | 4 |
| US-30 | E8 Entrega | Degradação graciosa (recomendação/agentes fora) | Should | 3 | 4 |
| US-31 | — | Integração com SIGAA/assinatura digital gov.br | Won't | 13 | — |

Total planejado (Must/Should/Could): **131 SP** (Sprint 0: 27 · Sprint 1: 19 · Sprint 2: 37 · Sprint 3: 29 · Sprint 4: 19).

## Épicos e histórias

### E1 — Fundação técnica

**US-01** — Como pessoa avaliadora, quero subir todo o sistema com um único comando, para avaliar o projeto sem configuração manual.
*Must · 5 SP · Sprint 0*
- **Dado** um host com Docker, Git e Make, **quando** executo `make env && make up`, **então** todos os containers ficam *healthy*.
- **Dado** o `.env.example` versionado, **quando** executo `make env`, **então** um `.env` com segredos aleatórios é criado e não é versionado.

**US-02** — Como equipe de desenvolvimento, quero componentes de software reutilizáveis e instaláveis, para não duplicar código entre os microsserviços.
*Must · 8 SP · Sprint 0*
- **Dado** um componente em `components/`, **quando** inspeciono o pacote, **então** ele tem `pyproject.toml` com versão semântica, interface pública no `__init__.py`, README e testes.
- **Dado** a suíte de testes do componente, **quando** executo `make test`, **então** a cobertura é de pelo menos 80%.
- **Dado** um serviço, **quando** sua imagem é construída, **então** os componentes são instalados a partir do caminho local.

**US-03** — Como cliente da API, quero um ponto único de entrada que valide o JWT e o papel, para centralizar a segurança e o roteamento.
*Must · 8 SP · Sprint 0*
- **Dado** uma rota protegida, **quando** chamo sem token válido, **então** recebo 401.
- **Dado** um papel sem permissão para a rota, **quando** chamo, **então** recebo 403 sem que a requisição chegue ao serviço.
- **Dado** um serviço fora do ar, **quando** chamo uma rota dele, **então** recebo 503 com o nome do serviço, e o *circuit breaker* abre após falhas consecutivas.

**US-04** — Como equipe, quero integração contínua com lint, testes e build, para detectar regressões a cada *push*.
*Should · 3 SP · Sprint 0*
- **Dado** um *push*, **quando** o GitHub Actions executa, **então** os jobs de `ruff`, testes e `docker compose build` rodam.

**US-05** — Como operador, quero que todo serviço exponha `/health`, `/ready` e `/version`, para saber se está saudável.
*Must · 3 SP · Sprint 0*
- **Dado** um serviço sem acesso ao banco ou ao broker, **quando** consulto `/ready`, **então** recebo 503 com o detalhe da verificação que falhou.
- **Dado** o gateway, **quando** consulto `GET /services`, **então** recebo status, versão, latência, banco e *uptime* de cada serviço.

### E2 — Identidade e acesso

**US-06** — Como usuário (estudante, empresa ou coordenação), quero me cadastrar e fazer login com meu papel, para acessar as funções do meu perfil.
*Must · 5 SP · Sprint 1*
- **Dado** um e-mail ainda não cadastrado, **quando** me registro, **então** a senha é armazenada com argon2 e o evento `user.registered` é publicado.
- **Dado** credenciais corretas, **quando** faço login, **então** recebo um JWT com expiração contendo meu papel.
- **Dado** credenciais incorretas, **quando** faço login, **então** recebo 401.
- **Dado** um cadastro com papel `coordinator`, **quando** não há token de serviço/coordenação, **então** recebo 403.

**US-07** — Como estudante, quero manter meu perfil acadêmico (curso, período, habilidades, resumo, disponibilidade, modalidade), para receber recomendações melhores.
*Must · 3 SP · Sprint 1*
- **Dado** que estou autenticado como estudante, **quando** salvo o perfil, **então** o evento `profile.updated` é publicado com o perfil completo.
- **Dado** uma disponibilidade acima de 30 h semanais, **quando** salvo, **então** recebo 422.

**US-08** — Como empresa concedente, quero manter o perfil da empresa, para que os estudantes conheçam a concedente.
*Should · 2 SP · Sprint 1*
- **Dado** que estou autenticado como empresa, **quando** salvo o perfil, **então** os dados ficam disponíveis em `GET /profiles/companies/{id}`.

### E3 — Vagas

**US-09** — Como empresa, quero publicar uma vaga com requisitos, curso, período mínimo, carga horária, modalidade e bolsa, para atrair estudantes.
*Must · 5 SP · Sprint 1*
- **Dado** uma vaga com jornada de até 6 h/dia e 30 h/semana, **quando** publico, **então** ela fica aberta e o evento `internship.published` é publicado.
- **Dado** uma vaga com jornada acima do limite legal, **quando** publico, **então** recebo 422.

**US-10** — Como estudante, quero buscar e filtrar vagas por texto, curso, modalidade e cidade, para encontrar oportunidades.
*Must · 3 SP · Sprint 1*
- **Dado** vagas publicadas, **quando** filtro por curso e modalidade, **então** vejo apenas as vagas abertas correspondentes, paginadas.

**US-11** — Como empresa, quero encerrar uma vaga, para parar de receber candidaturas.
*Should · 1 SP · Sprint 1*
- **Dado** uma vaga aberta da minha empresa, **quando** a encerro, **então** o status vira `closed` e o evento `internship.closed` é publicado; outra empresa recebe 403.

### E4 — Candidaturas e estágio

**US-12** — Como estudante, quero me candidatar a uma vaga, para concorrer ao estágio.
*Must · 3 SP · Sprint 2*
- **Dado** uma vaga aberta compatível com meu curso e período, **quando** me candidato, **então** a candidatura nasce em `submitted` e o evento `application.submitted` é publicado.
- **Dado** que já me candidatei à mesma vaga, **quando** tento de novo, **então** recebo 409.

**US-13** — Como empresa, quero analisar, aprovar ou rejeitar candidaturas seguindo a máquina de estados, para conduzir o processo seletivo.
*Must · 5 SP · Sprint 2*
- **Dado** uma candidatura `submitted`, **quando** inicio a análise, **então** ela vai para `under_review`.
- **Dado** uma candidatura `under_review`, **quando** aprovo informando início, fim, supervisor e seguro, **então** ela vai para `approved`.
- **Dado** uma transição não prevista (ex.: `submitted → active`), **quando** a solicito, **então** recebo 409.

**US-14** — Como coordenação, quero que as regras da Lei nº 11.788/2008 sejam validadas automaticamente, para garantir a conformidade legal.
*Must · 5 SP · Sprint 2*
- **Dado** uma jornada acima de 6 h/dia ou 30 h/semana, **quando** a empresa aprova, **então** recebo 422.
- **Dado** um estágio que ultrapassaria 2 anos na mesma concedente, **quando** a empresa aprova, **então** recebo 422 — exceto para estagiário PcD.
- **Dado** um estágio ativo, **quando** um relatório é recebido, **então** o próximo prazo é fixado em no máximo 6 meses.

**US-15** — Como estudante ou empresa, quero ver as candidaturas em um kanban por status, para acompanhar o processo.
*Should · 3 SP · Sprint 2*
- **Dado** candidaturas em vários status, **quando** abro a tela de candidaturas, **então** vejo uma coluna por status com as ações permitidas ao meu papel.

### E5 — Documentos

**US-16** — Como estudante e empresa, quero que o Termo de Compromisso de Estágio seja gerado automaticamente em PDF após a aprovação, para formalizar o estágio.
*Must · 8 SP · Sprint 2*
- **Dado** uma candidatura aprovada com seguro contra acidentes pessoais, **quando** o evento `application.status_changed` chega ao `document-service`, **então** o PDF é gerado, o evento `agreement.generated` é publicado e a candidatura passa a `agreement_pending`.
- **Dado** uma aprovação sem apólice de seguro, **quando** o TCE seria gerado, **então** ele não é gerado.

**US-17** — Como coordenação, quero aprovar o TCE, para que o estágio passe a ativo.
*Must · 3 SP · Sprint 2*
- **Dado** um TCE pendente, **quando** a coordenação aprova, **então** `agreement.approved` é publicado e o estágio passa a `active`.

**US-18** — Como estudante, quero enviar relatórios de atividades com versões, para cumprir a periodicidade legal.
*Must · 5 SP · Sprint 2*
- **Dado** um estágio ativo, **quando** envio um relatório (PDF), **então** ele é armazenado como versão 1 e `report.submitted` é publicado.
- **Dado** um relatório existente, **quando** envio nova versão, **então** a versão anterior é preservada.

### E6 — Notificações

**US-19** — Como usuário, quero receber notificações a cada transição relevante, para ficar informado sem consultar cada tela.
*Must · 5 SP · Sprint 2*
- **Dado** qualquer evento do fluxo principal, **quando** ele é consumido, **então** os atores envolvidos recebem uma notificação na caixa de entrada.
- **Dado** o mesmo evento entregue duas vezes, **quando** é consumido, **então** apenas uma notificação é criada (idempotência).

### E7 — Inteligência

**US-20** — Como estudante, quero ver vagas recomendadas com a explicação do porquê, para escolher onde me candidatar.
*Must · 8 SP · Sprint 3*
- **Dado** um perfil preenchido, **quando** abro as recomendações, **então** vejo as vagas ordenadas por *score* com habilidades em comum e requisitos faltantes.
- **Dado** um perfil vazio, **quando** abro as recomendações, **então** vejo vagas recentes e populares (*cold start*).

**US-21** — Como empresa, quero ver o ranking dos candidatos de uma vaga, para priorizar a análise.
*Must · 5 SP · Sprint 3*
- **Dado** uma vaga com candidaturas, **quando** abro o ranking, **então** os candidatos aparecem ordenados por *score* com a justificativa.

**US-22** — Como equipe, quero avaliar o recomendador offline com precision@5 e nDCG@5 contra *baselines*, para medir sua qualidade.
*Should · 3 SP · Sprint 3*
- **Dado** o conjunto rotulado sintético do seed, **quando** executo `make eval`, **então** obtenho uma tabela com o modelo híbrido, o *baseline* aleatório e o *baseline* só-filtros.

**US-23** — Como estudante, quero um assistente de IA que explique por que uma vaga combina comigo, sugira melhorias no perfil e gere um rascunho de carta de motivação.
*Could · 5 SP · Sprint 3*
- **Dado** que não há `ANTHROPIC_API_KEY`, **quando** uso o assistente, **então** ele responde em modo regras com a mesma API e a interface mostra "IA em modo regras".
- **Dado** uma execução, **quando** ela termina, **então** a trilha de chamadas de ferramentas fica visível.

**US-24** — Como coordenação, quero um agente de acompanhamento que alerte sobre relatórios a vencer, limites de 2 anos e jornada, para agir a tempo.
*Should · 5 SP · Sprint 3*
- **Dado** um estágio com relatório vencendo em até 30 dias, **quando** o agente roda (agendado ou sob demanda), **então** `report.due_soon` é publicado e os envolvidos são notificados.
- **Dado** qualquer execução, **quando** termina, **então** nenhuma candidatura teve o status alterado pelo agente.

**US-25** — Como empresa, quero um agente de triagem que resuma o ranking de candidatos com justificativas.
*Could · 3 SP · Sprint 3*
- **Dado** uma vaga com candidatos, **quando** executo a triagem, **então** recebo um resumo baseado na saída do `recommendation-service`.

### E8 — Qualidade e entrega

**US-26** — Como pessoa avaliadora, quero uma tela com o status de todos os microsserviços, para verificar a arquitetura em execução.
*Must · 3 SP · Sprint 4*
- **Dado** a stack no ar, **quando** abro "Status dos Microsserviços", **então** vejo nome, status, versão, latência, banco e *uptime*, atualizados automaticamente.

**US-27** — Como pessoa avaliadora, quero ver na interface quais microsserviços forneceram cada dado, para entender a composição da tela.
*Must · 3 SP · Sprint 4*
- **Dado** qualquer painel, **quando** ele é exibido, **então** mostra um *badge* com o serviço lido de `X-Served-By`.
- **Dado** o *toggle* "Mostrar microsserviços" ligado, **quando** navego, **então** cada painel é destacado com a cor do seu serviço.

**US-28** — Como equipe, quero um teste e2e do fluxo principal via gateway, para garantir que a demonstração funciona.
*Must · 5 SP · Sprint 4*
- **Dado** a stack no ar, **quando** executo `make e2e`, **então** o fluxo cadastro → vaga → recomendação → candidatura → aprovação → TCE → coordenação → relatório → notificações passa.

**US-29** — Como equipe, quero o relatório gerado automaticamente em DOCX e PDF com prints da interface.
*Must · 5 SP · Sprint 4*
- **Dado** os prints gerados por `make screenshots`, **quando** executo `make report`, **então** `relatorio.docx` e `relatorio.pdf` são gerados sem erro.

**US-30** — Como usuário, quero que o sistema continue funcionando se a recomendação ou os agentes caírem, para não perder o acesso às demais funções.
*Should · 3 SP · Sprint 4*
- **Dado** o `recommendation-service` parado, **quando** abro o dashboard, **então** as demais seções funcionam e um aviso é exibido.

**US-31** — Como coordenação, quero integração com o SIGAA e assinatura digital gov.br. *Won't (fora do escopo desta entrega) · 13 SP*
