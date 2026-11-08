# eh_auth

Componente de autenticação e autorização do EstágioHub: emissão e validação de
JWT (HS256), *hashing* de senha com argon2id e dependências FastAPI para exigir
autenticação e papéis.

## Interface fornecida

| Símbolo | Tipo | Descrição |
|---|---|---|
| `JWTAuth(secret, algorithm, expires_minutes, issuer)` | classe | `create_token(...)`, `create_service_token(name)`, `decode(token) -> Principal`. |
| `Principal(id, role, name, email)` | dataclass | Quem está chamando; `is_service` para tokens internos. |
| `Role` | enum | `student`, `company`, `coordinator`, `service`. |
| `TokenError` | exceção | Token ausente, expirado, adulterado ou com *claims* inválidas. |
| `hash_password(pw)` / `verify_password(pw, hash)` / `needs_rehash(hash)` | funções | argon2id com sal embutido. |
| `install_auth(app, auth)` | função | Registra a instância `JWTAuth` em `app.state`. |
| `get_current_principal` / `get_optional_principal` | dependências | Exigem (401) ou tornam opcional o token *Bearer*. |
| `require_role(*roles)` | fábrica de dependência | Responde 401 sem token e 403 para papéis não permitidos. |

## Interface requerida

- `PyJWT >= 2.8`, `argon2-cffi >= 23.1`, `fastapi >= 0.115`.
- Um segredo compartilhado com pelo menos 32 caracteres (variável `JWT_SECRET`,
  gerada por `make env`).

## Exemplo de uso

```python
from fastapi import Depends, FastAPI
from eh_auth import JWTAuth, Principal, Role, install_auth, require_role

app = FastAPI()
install_auth(app, JWTAuth(settings.jwt_secret))

@app.post("/internships")
async def publish(principal: Principal = Depends(require_role(Role.COMPANY))):
    ...
```

## Serviços que reutilizam

Todos os serviços de negócio (`user-service` também emite os tokens), o
`api-gateway` (validação na borda) e o `agent-service` (token de serviço para
o agente agendado).
