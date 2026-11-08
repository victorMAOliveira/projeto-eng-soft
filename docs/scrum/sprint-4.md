# Sprint 4 — Qualidade e entrega

- **Período:** [PREENCHER: data/hora de início e fim — usar os timestamps do primeiro e do último commit da sprint (`git log sprint-3..sprint-4`)]
- **Duração planejada:** cerca de 2 horas
- **Tag:** `sprint-4`

## Meta da sprint

Deixar o produto pronto para entrega e defesa: tela de status e destaque dos
microsserviços na interface, dados de demonstração, teste e2e do fluxo
principal, prints automatizados, relatório gerado em DOCX e PDF, guia de
estudo e versão 1.0.0 de todos os pacotes — validado pelo gate final a partir
de um estado limpo.

## Histórias selecionadas

| ID | História | SP |
|---|---|---|
| US-26 | Tela de status dos microsserviços | 3 |
| US-27 | Destaque dos microsserviços na interface | 3 |
| US-28 | Teste e2e do fluxo principal | 5 |
| US-29 | Relatório gerado em DOCX e PDF com prints | 5 |
| US-30 | Degradação graciosa (recomendação/agentes fora) | 3 |
| | **Total** | **19** |

## Tarefas técnicas

| Tarefa | História | Estimativa |
|---|---|---|
| Página `/status` com auto-refresh (HTMX, 5 s) e tabela de rotas; legenda de serviços no dashboard | US-26, US-27 | 0,75 h |
| `scripts/seed.py` (idempotente, via gateway, estados de demonstração) | US-28 | 0,75 h |
| `scripts/e2e_demo.py` (9 etapas do fluxo principal com asserções) | US-28 | 0,5 h |
| `scripts/capture_screenshots.py` (fluxo pela interface + telas de degradação) e imagem Playwright | US-27, US-29, US-30 | 1 h |
| `scripts/reuse_metrics.py`, diagramas Mermaid, `build_report.py`, `render_pandoc.sh`, `reference.docx`, `style.css` | US-29 | 1 h |
| `docs/relatorio/relatorio.md`, `docs/STUDY_GUIDE.md`, README | US-29 | 1,5 h |
| Versão 1.0.0 de componentes e serviços; gate final | — | 0,5 h |

## Definition of Done

- [x] Código com *docstrings*.
- [x] Testes passando (`make test`) e e2e passando (`make e2e`).
- [x] `ruff` sem erros.
- [x] Todos os 17 containers *healthy* (`make up`).
- [x] Documentação atualizada (relatório, guia de estudo, README, PROGRESS.md).

## Review — o que foi entregue

| Entrega | Evidência |
|---|---|
| Status, legenda, seed, e2e, prints, diagramas, pipeline do relatório | commit `88ff025` |
| Legendas das tabelas, guia de estudo, README, versão 1.0.0, relatório gerado | commits seguintes, tag `sprint-4` |

Evidências de execução (gate final, a partir de `make clean`):

- `make up`: 17 containers *healthy*;
- `make seed`: 8 empresas, 30 vagas, 51 estudantes, candidaturas e estados de
  demonstração (TCEs pendentes, estágios ativos com relatório a vencer, vencido
  e perto do limite de 2 anos);
- `make test`: lint e todos os testes aprovados (tabela 9 do relatório);
- `make e2e`: 9 de 9 etapas aprovadas;
- `make eval`: métricas do recomendador e de reuso geradas;
- `make screenshots`: 26 telas (23 do fluxo + 3 de degradação);
- `make report`: `docs/relatorio/build/relatorio.docx` e `relatorio.pdf`.

## Problemas técnicos encontrados e soluções

1. **Imagem do Playwright sem o pacote Python.** A imagem
   `mcr.microsoft.com/playwright/python` traz os navegadores, mas não o pacote
   `playwright` (`ModuleNotFoundError`). Solução: imagem fina
   (`scripts/screenshots.Dockerfile`) que instala `playwright==1.49.1`, a mesma
   versão dos navegadores.
2. **Mermaid CLI sem navegador.** Ao trocar o *entrypoint* para renderizar
   vários arquivos, perdeu-se a configuração do Puppeteer da imagem (caminho do
   Chromium). Solução: usar o `/puppeteer-config.json` da própria imagem.
3. **Diagrama de contêineres ilegível.** A primeira versão desenhava cada
   chamada REST e ficou poluída. Solução: visão em três camadas
   (borda → serviços → um banco por serviço) com o *broker* ao lado; as
   chamadas síncronas ficaram documentadas nas tabelas da seção 6.3.
4. **Legendas de tabela soltas no Pandoc.** Os marcadores de blocos gerados
   (comentários HTML) separavam a tabela da linha `Table:`, e o Pandoc não
   associava a legenda. Solução: a legenda passou a ficar no próprio marcador
   (`<!-- BEGIN:x | legenda -->`) e o script a emite colada à tabela.
5. **Sumário antes da capa.** O Pandoc coloca o sumário no início do HTML.
   Solução: o passo de PDF move o sumário para depois da capa (DOM) e o DOCX usa
   um campo de sumário do Word inserido após a capa.
6. **Hifenização no título exato da capa** ("Com-ponentes") — desativada na
   capa e nos títulos.
7. **Barra lateral cortada nos prints de página inteira** (altura fixa em
   `100vh`) — o fundo da coluna passou a ser desenhado no contêiner.
8. **Perfil do estudante de demonstração pouco coerente.** As habilidades
   sorteadas combinavam mal com a vaga do roteiro. Solução: perfil fixo apenas
   para a conta `estudante@ufal.test`; as demais 49 contas não mudaram. O nDCG@5
   do híbrido passou de 0,968 para 0,965 (valor atualizado no relatório).
9. **Ordem do roteiro de prints.** Vagas já candidatadas saem das
   recomendações; o assistente de IA passou a ser executado antes da
   candidatura.

## Retrospectiva

[PREENCHER: retrospectiva da equipe — o que foi bem, o que melhorar, ações]
