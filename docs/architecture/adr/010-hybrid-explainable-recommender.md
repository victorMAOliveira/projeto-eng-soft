# ADR-010 — Recomendador híbrido, explicável e determinístico (sem LLM)

**Status:** Aceito · **Sprint:** 3

## Contexto

Estudantes precisam de vagas recomendadas com a justificativa do "porquê" e
empresas precisam de um ranking de candidatos. O resultado deve ser
reproduzível (avaliação offline, testes) e funcionar sem dependência externa.

## Decisão

- `recommendation-service` com um **modelo de leitura** próprio (CQRS leve):
  tabelas `rm_students`, `rm_internships` e `rm_applications`, alimentadas
  pelos eventos `user.registered`, `profile.updated`, `internship.published`,
  `internship.closed`, `application.submitted` e `application.status_changed`.
  `POST /recommendations/rebuild` reconstrói o modelo via REST (recuperação).
- Algoritmo puro em `recommender.py`: filtros duros (curso, período,
  disponibilidade, vaga aberta, jornada legal) → TF-IDF (unigramas+bigramas,
  sem acentos, *stop words* pt-BR) com cosseno → Jaccard de habilidades →
  bônus de preferência (modalidade/cidade) → `score = 0,50·cos + 0,35·Jaccard +
  0,15·pref` (pesos por variável de ambiente) → explicação textual.
- *Cold start*: perfil vazio ⇒ 60% recência (meia-vida de 14 dias) + 40%
  popularidade.
- Empates desfeitos pelo id ⇒ resultado determinístico.
- Avaliação offline (`make eval`) com conjunto **sintético** rotulado por
  trilha latente, comparando com *baselines* aleatório e só-filtros.

## Consequências

- (+) Cada recomendação traz habilidades em comum, faltantes e o filtro que
  eliminou a vaga — base também para o agente de IA.
- (+) Sem custo por requisição e sem rede externa.
- (−) TF-IDF não captura sinônimos ("APIs REST" × "web services"); embeddings
  seriam a evolução natural.
- (−) O modelo de leitura é eventualmente consistente (alguns milissegundos).
