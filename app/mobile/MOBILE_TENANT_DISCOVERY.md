# Discovery de municípios (app mobile)

Catálogo independente de `public.city` e de `/city`. Tabela: `public.mobile_city_directory`.

## Endpoint

`GET /mobile/v1/available-cities` — público, sem JWT, schema `public`.

## Fluxo

1. App chama a **API central** (`https://prod-api.afirmeplay.com.br`).
2. Usuário escolhe município na lista.
3. App persiste `api_base_url` (e opcionalmente `slug`, `tenant_code`, `id` do catálogo).
4. Todas as operações mobile (`/offline-pack/redeem`, `/auth/login`, `/sync/*`) usam essa base URL.

## Cadastrar município

Inserir em `public.mobile_city_directory` (SQL ou script):

```bash
python scripts/seed_mobile_city_directory.py
```

Campos obrigatórios: `city_name`, `city_slug` (único), `tenant_code` (único), `api_base_url`, `hosting_mode` (`shared`|`dedicated`).

## VPS dedicada

1. Deploy do backend na VPS do cliente (mesmo código).
2. Códigos/registry permanecem **no Postgres local** dessa VPS.
3. Na **API central**, inserir linha com `hosting_mode=dedicated` e `api_base_url` apontando para a API da VPS (ex. `https://api.cliente.com.br`).
4. `mobile_visible=true`, `is_active=true`.

Municípios na VPS central: `hosting_mode=shared`, `api_base_url=https://prod-api.afirmeplay.com.br` (uma linha por município exibido no app).

## Migração

```bash
flask db upgrade
# ou: alembic upgrade head
```

Revision: `add_mobile_city_directory`.
