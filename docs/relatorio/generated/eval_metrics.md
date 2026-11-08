| Estratégia | Precision@5 | nDCG@5 |
|---|---|---|
| Baseline aleatório | 0,151 | 0,151 |
| Baseline só filtros (mais recentes) | 0,708 | 0,825 |
| Híbrido (0,50·cos + 0,35·Jaccard + 0,15·pref) | 0,725 | 0,968 |
| Ablação: só conteúdo (TF-IDF/cosseno) | 0,721 | 0,978 |
| Ablação: só atributos (Jaccard) | 0,725 | 0,970 |

Dados **sintéticos** (seed 2026): 48 estudantes avaliados, 30 vagas, k = 5; baseline aleatório = média de 30 sorteios por estudante. Rótulos: 2 = mesma trilha latente e elegível; 1 = trilha adjacente e elegível; 0 = demais.
