# ADR-011 — Agentes de IA com *tool use* e fallback em modo regras

**Status:** Aceito · **Sprint:** 3

## Contexto

O enunciado marca os agentes de IA como opcionais. Eles dependem de uma chave
de API externa que pode não estar disponível na apresentação, e não podem
tomar decisões que cabem às pessoas (aprovar ou rejeitar candidaturas).

## Decisão

- `agent-service` com três agentes: Assistente de Candidatura (estudante),
  Agente de Acompanhamento (coordenação; agendado com APScheduler e sob
  demanda) e Agente de Triagem (empresa).
- Modo IA: SDK oficial da Anthropic (Messages API com *tool use*), laço manual
  limitado a **6 passos** (chamadas ao modelo) e com *timeout*; modelo em
  `LLM_MODEL` (padrão `claude-haiku-5-5`).
- Modo regras: sem `ANTHROPIC_API_KEY` (ou se a IA falhar, recusar, estourar
  passos ou *timeout*), um plano fixo chama as **mesmas ferramentas** e compõe a
  resposta por *templates*; a API é idêntica e a interface mostra
  "IA em modo regras".
- *Guardrails*: as ferramentas só leem, sugerem ou notificam
  (`send_notification`, `check_deadlines` → `report.due_soon`); não existe
  ferramenta nem cliente HTTP capaz de mudar status de candidatura; cada agente
  só enxerga a sua lista de ferramentas; o estudante só consulta o próprio
  perfil.
- Cada chamada ao modelo e a ferramentas é gravada (`agent_runs`,
  `agent_steps`) e exibida como "trilha de execução"; alertas são deduplicados
  (`alerts_sent`).
- Nos testes o cliente LLM é sempre substituído por um dublê programável.

## Consequências

- (+) A demonstração funciona sem chave e sem internet.
- (+) Auditoria completa do que o agente fez.
- (−) No modo regras as respostas são menos naturais (texto por *templates*).
