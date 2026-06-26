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

### Via API Admin (Recomendado)

Use as rotas administrativas (requer role `admin`).

**Endpoint:** `POST /mobile/v1/admin/cities`

#### Opção 1: Município na VPS Central (shared)

Adiciona município que JÁ EXISTE em `public.city`:

```json
POST /mobile/v1/admin/cities
{
  "city_id": "abc-123-def",
  "hosting_mode": "shared"
}
```

Dados preenchidos automaticamente:
- `city_name` - de City.name
- `city_slug` - de City.slug
- `tenant_code` - gerado do city_id
- `api_base_url` - URL central

#### Opção 2: Município em VPS Dedicada

Cliente com infraestrutura própria (NÃO existe em public.city):

```json
POST /mobile/v1/admin/cities
{
  "city_name": "Cliente XYZ",
  "city_slug": "cliente-xyz",
  "tenant_code": "XYZ001",
  "hosting_mode": "dedicated",
  "api_base_url": "https://api.clientexyz.com.br"
}
```

### Listar Municípios Disponíveis

Para ver quais municípios da VPS central ainda NÃO estão no mobile:

```
GET /mobile/v1/admin/cities/available-for-mobile
```

### Via Script (legado)

```bash
python scripts/seed_mobile_city_directory.py
```

## VPS dedicada

1. Deploy do backend na VPS do cliente (mesmo código).
2. Códigos/registry permanecem **no Postgres local** dessa VPS.
3. Na **API central**, usar endpoint admin para adicionar com `hosting_mode=dedicated`.
4. Fornecer `api_base_url` apontando para a API da VPS (ex. `https://api.cliente.com.br`).

Municípios na VPS central: `hosting_mode=shared`, dados preenchidos automaticamente.

## Rotas Administrativas

Veja documentação completa em `app/routes/mobile/README_ADMIN_API.md`.

**Rotas disponíveis:**
- `GET /mobile/v1/admin/cities/available-for-mobile` - Listar municípios disponíveis para adicionar
- `POST /mobile/v1/admin/cities` - Adicionar município (shared ou dedicated)
- `GET /mobile/v1/admin/cities` - Listar todos
- `GET /mobile/v1/admin/cities/:id` - Buscar um
- `PUT /mobile/v1/admin/cities/:id` - Atualizar (mobile_visible, is_active, sort_order)
- `DELETE /mobile/v1/admin/cities/:id` - Desativar (soft delete)
- `GET /mobile/v1/admin/cities/config/central-api-url` - Obter URL central

## Migração

```bash
flask db upgrade
```

Migrations:
- `add_mobile_city_directory` - Cria tabela
- `20260625_add_city_id_to_mobile_directory` - Adiciona FK opcional city_id
