# ADR-008 — Documentos: MongoDB para metadados e volume para arquivos

**Status:** Aceito · **Sprint:** 2

## Contexto

O `document-service` guarda o TCE (PDF gerado) e relatórios de atividades com
várias versões. Os metadados são documentos com listas aninhadas (versões) e
formato que evolui; os arquivos são binários de até 5 MB.

## Decisão

- Metadados no MongoDB (coleções `agreements`, `reports` e
  `processed_events`), acessados por um *port* `DocumentCollection` com dois
  *adapters*: `MongoCollection` (driver assíncrono do PyMongo) e
  `InMemoryCollection` (testes).
- Binários no volume nomeado `document-files`, via `FileStorage`, que bloqueia
  *path traversal*.
- PDF gerado com ReportLab; pré-visualização PNG da 1ª página com pypdfium2.
- O TCE só é emitido com seguro contra acidentes pessoais (art. 9º, IV): a
  regra é verificada na aprovação (`application-service`) e de novo na geração
  (`document-service`), em defesa em profundidade.

## Consequências

- (+) Versões ficam no próprio documento do relatório (`$push`), sem *joins*.
- (+) Testes rápidos sem MongoDB, pela inversão de dependência.
- (−) O volume não é replicado; em produção seria um *object storage* (S3/MinIO).
