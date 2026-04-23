# Multi-tenant (ORM): schema por município

Este pacote concentra a resolução de **tenant** (cidade/município) e o uso de **sessões SQLAlchemy** que traduzem o schema lógico `tenant` para o schema físico do PostgreSQL.

**Importante:** no banco, **todo** schema de município é `city_<uuid>` (função `city_id_to_schema_name`). **Não** há schemas `tenant_*` no PostgreSQL; `tenant` nos models é só rótulo lógico do ORM.

## Conceitos

### Schema lógico `tenant` nos models

Tabelas de dados do município usam:

```python
__table_args__ = {"schema": "tenant"}
```

No runtime, `TenantAwareSession` / `DatabaseSessionFactory` aplicam `schema_translate_map` (`tenant` → `city_...`). Assim, o mesmo código ORM gera SQL no schema físico `city_*` sem alterar os modelos por cidade.

### Schema `public`

Tabelas globais (ex.: `city`, `users`, `question`) continuam com `schema="public"` ou sem schema equivalente a `public`.

### Foreign keys

Após definir `schema="tenant"`, o metadata precisa saber **qual tabela física** cada FK aponta. Duas formas válidas:

1. **String qualificada** (pode falhar em alguns casos com o schema lógico `tenant`):  
   `db.ForeignKey('tenant.school.id')`, `db.ForeignKey('public.users.id')`, etc.

2. **Referência à coluna do modelo (recomendado para tabelas tenant)** — o join no metadata fica estável:  
   `db.ForeignKey(OutroModel.__table__.c.id)` com `import` do modelo referenciado.

Referências a tabelas globais:

- `db.ForeignKey('public.users.id')` ou `User.__table__.c.id` se `users` estiver em `public`.

Referências **tenant → public** (ex.: sessão de prova em `public.test_sessions`):

- `db.ForeignKey(TestSession.__table__.c.id)` ou `db.ForeignKey('public.test_sessions.id')`.

Isso evita erros de mapper do tipo “could not find table `play_tv_videos` / `forms` / `school`”.

### Relacionamentos `backref` vs `back_populates`

Se **os dois lados** declaram o relacionamento (ex.: `Certificate.template` e `CertificateTemplate.certificates`), use **`back_populates`** nos dois lados. Não use `backref='template'` no pai se o filho já tem `template = db.relationship(...)` — o SQLAlchemy tenta criar a mesma propriedade duas vezes e falha ao inicializar os mappers.

### Relacionamentos entre tenant e public

Quando uma coluna FK aponta para **outro schema** (ex.: `tenant.evaluation_results` → `public.test_sessions`), o SQLAlchemy **nem sempre infere** o `relationship`. É necessário declarar **`primaryjoin`** e **`foreign_keys`** explicitamente, como em `EvaluationResult.session` → `TestSession`.

## Request HTTP: o que fica em `flask.g`

O middleware em `app/utils/tenant_middleware.py` pode preencher, entre outros:

- `g.request_context` — contexto resolvido (cidade, `tenant_schema` = nome físico `city_*` ou `public`, flags).
- `g.public_session` — sessão extra só `public` (quando usada).
- `g.tenant_session` — normalmente `None`; a tradução `tenant` → `city_*` fica em `db.session` (`TenantAwareSession`).

No teardown (`app/__init__.py`), `db.session`, `g.public_session` e sessões explícitas recebem commit/rollback e fechamento.

### Modo legado (`search_path`)

Se `LEGACY_SEARCH_PATH_ENABLED` estiver ativo (padrão conforme configuração do projeto), o middleware pode ainda executar `SET search_path` para compatibilidade com código que usa apenas `db.session`. A direção desejada é usar **`get_orm_session()`** nas rotas migradas.

## `get_orm_session()` (`app/multitenant/flask_g.py`)

Em geral equivale a **`db.session`**, que já é `TenantAwareSession` e aplica o mapa quando há município. Só diverge se algum fluxo definir **`g.tenant_session`** explicitamente (legado).

Exemplo:

```python
from app.multitenant.flask_g import get_orm_session

get_orm_session().query(School).filter_by(...).all()
get_orm_session().add(obj)
get_orm_session().commit()
```

Mantenha `db.func`, `db.or_`, etc., via `from app import db` quando precisar.

## Resolução de tenant (resumo)

Regras detalhadas estão no docstring de `app/utils/tenant_middleware.py`. Em geral:

1. JWT com `city_id` do usuário.
2. Headers `X-City-ID` / `X-City-Slug` (admin).
3. Subdomínio do `Host` (slug do município).

## Checklist para novas rotas ou models

1. Dados do município: model com `schema="tenant"` e FKs qualificadas (`tenant.*` / `public.*`).
2. Queries na rota: preferir `get_orm_session()`.
3. Relação entre tabela tenant e tabela public: conferir se o `relationship` precisa de `primaryjoin` / `foreign_keys`.
4. Após mudanças nos mappers, subir a aplicação e exercitar o fluxo (ex.: `/subdomain/check?subdomain=...`).

## Models fora de `app/models/`

Alguns modelos (ex.: `AnswerSheetGabaritoGeneration`) ficam em `app/services/...` e também usam `schema="tenant"`. **Todas** as FKs para tabelas tenant precisam do prefixo `tenant.` (ex.: `tenant.answer_sheet_gabaritos.id`), como nos modelos em `app/models/`.

## Rotas de subdomínio (slug do município)

O blueprint de verificação de slug está registrado em:

- `/subdomain/check`
- `/api/subdomain/check` (alias para o mesmo handler; útil quando o frontend chama a API com prefixo `/api`)

Ambos aceitam `GET` e `OPTIONS`. Parâmetro de query: `subdomain` (ex.: `jaru`).

O `tenant_middleware` trata **`GET`**, **`HEAD`** e **`OPTIONS`** nessas URLs com contexto **`public` apenas** (sem `resolve_tenant_context()`), para a consulta a `public.city` na view não depender de JWT, Origin ou subdomínio — evitando 400/404 antes da resposta `{ "exists": true|false }`.

O **`OPTIONS`** em **`/login`** (e `/api/login` se existir) também usa o mesmo atalho `public` — só o **preflight**; o **`POST`** de login continua passando por `resolve_tenant_context()` para validação de subdomínio/município.

## Referências de código

| Peça | Arquivo |
|------|---------|
| `schema_translate_map` no bind do request (`db.session`) | `app/multitenant/tenant_aware_session.py` |
| Fábrica de sessões explícitas (ex.: `get_public_session`) | `app/multitenant/db_session_factory.py` |
| `get_orm_session` | `app/multitenant/flask_g.py` |
| Middleware / contexto | `app/utils/tenant_middleware.py` |
| Teardown de sessões | `app/__init__.py` |
| Exemplo FK + relationship cross-schema | `app/models/evaluationResult.py`, `app/models/testSession.py` |
| Geração de cartão (modelo tenant em `services/`) | `app/services/cartao_resposta/answer_sheet_gabarito_generation.py` |
