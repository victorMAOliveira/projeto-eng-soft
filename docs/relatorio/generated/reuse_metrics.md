| Serviço | LOC específicas | LOC reutilizadas (componentes) | Componentes usados | Taxa de reuso |
|---|---|---|---|---|
| agent-service | 1059 | 1144 | 5 | 51,9% |
| api-gateway | 317 | 507 | 3 | 61,5% |
| application-service | 982 | 1144 | 5 | 53,8% |
| document-service | 807 | 980 | 4 | 54,8% |
| internship-service | 322 | 1011 | 4 | 75,8% |
| notification-service | 375 | 847 | 3 | 69,3% |
| recommendation-service | 875 | 1144 | 5 | 56,7% |
| user-service | 492 | 1011 | 4 | 67,3% |
| web-frontend | 2320 | 722 | 3 | 23,7% |
| **Total** | **7549** | **8510** | — | **53,0%** |

| Componente | LOC | Serviços que reutilizam |
|---|---|---|
| eh_auth | 161 | 8 |
| eh_events | 473 | 7 |
| eh_db | 164 | 5 |
| eh_observability | 213 | 9 |
| eh_http | 133 | 6 |
| eh_ui | 376 | 1 |

Sem componentes, o código comum seria copiado em cada serviço: 16059 LOC no total, contra 9069 LOC com componentes — **6990 LOC evitadas**.
