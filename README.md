# EstágioHub

Sistema de gerenciamento de estágios universitários (Lei nº 11.788/2008)
construído com **microsserviços** e **componentes de software**.

> Projeto da disciplina Engenharia de Software — UFAL, Instituto de Computação.
> Em construção: este README é completado a cada sprint (ver `PROGRESS.md`).

## Pré-requisitos

Docker (com Compose v2), Git e GNU Make. Nada mais precisa ser instalado no
host: testes, seed, relatório e prints rodam em containers.

## Como executar

```bash
make env   # cria .env e gera segredos aleatórios
make up    # constrói e sobe a stack, esperando todos ficarem healthy
```

- API Gateway: <http://localhost:8000> (`GET /services` mostra a saúde de todos os serviços)
- Painel do RabbitMQ: <http://localhost:15672>
