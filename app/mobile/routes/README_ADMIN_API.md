# API Admin - Catalogo de Municipios Mobile

**Atualizado: 25/06/2026**

Rotas administrativas para adicionar municipios ao catalogo mobile do app.

**Autenticacao:** Todas as rotas requerem JWT com role `admin`.

---

## Dois Fluxos Principais

### 1. Adicionar Municipio da VPS Central (shared)
- Municipio JA EXISTE em `public.city`
- Admin fornece apenas o `city_id`
- Dados preenchidos automaticamente (nome, slug, URL, tenant_code)

### 2. Adicionar Municipio de VPS Dedicada (dedicated)
- Cliente com infraestrutura propria
- Admin fornece todos os dados manualmente
- NAO existe em `public.city`

---

## Endpoints

### 1. Listar Municipios Disponiveis

`GET /mobile/v1/admin/cities/available-for-mobile`

**Descricao:** Retorna municipios da VPS central que ainda NAO estao no catalogo mobile.

**Resposta (200):**
```json
{
  "total": 3,
  "cities": [
    {
      "id": "abc-123-def",
      "name": "Sao Paulo",
      "state": "SP",
      "slug": "sao-paulo",
      "plan_code": "premium"
    },
    {
      "id": "xyz-456-uvw",
      "name": "Rio de Janeiro",
      "state": "RJ",
      "slug": "rio-de-janeiro",
      "plan_code": "basic"
    }
  ]
}
```

---

### 2. Adicionar Municipio ao Mobile

`POST /mobile/v1/admin/cities`

#### Modo 1: VPS Central (shared)

**Payload:**
```json
{
  "city_id": "abc-123-def",
  "hosting_mode": "shared",
  "mobile_visible": true,
  "is_active": true,
  "sort_order": 0
}
```

**Resposta (201):**
```json
{
  "mensagem": "Municipio 'Sao Paulo' adicionado ao catalogo mobile com sucesso",
  "info": "Dados preenchidos automaticamente a partir do municipio da VPS central",
  "data": {
    "id": "novo-uuid",
    "city_id": "abc-123-def",
    "city_name": "Sao Paulo",
    "city_slug": "sao-paulo",
    "tenant_code": "ABC123DE",
    "api_base_url": "https://prod-api.afirmeplay.com.br",
    "hosting_mode": "shared",
    "mobile_visible": true,
    "is_active": true,
    "sort_order": 0
  }
}
```

**Campos automaticos (shared):**
- `city_name` - copiado de City.name
- `city_slug` - copiado de City.slug
- `tenant_code` - gerado automaticamente (primeiros 8 chars do city_id)
- `api_base_url` - URL central (variavel de ambiente)

#### Modo 2: VPS Dedicada (dedicated)

**Payload:**
```json
{
  "city_name": "Cliente XYZ",
  "city_slug": "cliente-xyz",
  "tenant_code": "XYZ001",
  "hosting_mode": "dedicated",
  "api_base_url": "https://api.clientexyz.com.br",
  "mobile_visible": true,
  "is_active": true,
  "sort_order": 1
}
```

**Resposta (201):**
```json
{
  "mensagem": "Municipio 'Cliente XYZ' (VPS dedicada) adicionado ao catalogo mobile",
  "data": {
    "id": "novo-uuid",
    "city_id": null,
    "city_name": "Cliente XYZ",
    "city_slug": "cliente-xyz",
    "tenant_code": "XYZ001",
    "api_base_url": "https://api.clientexyz.com.br",
    "hosting_mode": "dedicated",
    "mobile_visible": true,
    "is_active": true,
    "sort_order": 1
  }
}
```

---

### 3. Listar Todos

`GET /mobile/v1/admin/cities`

Retorna todos os municipios (incluindo inativos).

---

### 4. Buscar Um

`GET /mobile/v1/admin/cities/:id`

Retorna detalhes de um municipio especifico.

---

### 5. Atualizar

`PUT /mobile/v1/admin/cities/:id`

**Campos editaveis:**
- `mobile_visible`
- `is_active`
- `sort_order`

**Campos NAO editaveis:**
- `city_id` (imutavel)
- `hosting_mode` (imutavel)
- `city_name`, `city_slug`, `tenant_code`, `api_base_url` (imutaveis)

**Payload:**
```json
{
  "mobile_visible": false,
  "sort_order": 10
}
```

---

### 6. Desativar

`DELETE /mobile/v1/admin/cities/:id`

Soft delete: define `is_active=false` e `mobile_visible=false`.

---

### 7. Obter URL Central

`GET /mobile/v1/admin/cities/config/central-api-url`

Retorna URL da API central configurada.

---

## Erros Comuns

### 400 - city_id obrigatorio (shared)
```json
{
  "erro": "city_id e obrigatorio para hosting_mode='shared'",
  "dica": "Forneca o ID do municipio existente em public.city"
}
```

### 404 - Municipio nao existe
```json
{
  "erro": "Municipio nao encontrado",
  "detalhes": "Nao existe municipio com id=xyz na VPS central"
}
```

### 409 - Municipio ja esta no catalogo
```json
{
  "erro": "Municipio ja esta no catalogo mobile",
  "detalhes": "Sao Paulo ja foi adicionado ao app mobile",
  "mobile_entry_id": "uuid"
}
```

### 409 - Slug ou tenant_code duplicado
```json
{
  "erro": "Ja existe um municipio com este slug no catalogo mobile",
  "detalhes": "city_slug deve ser unico"
}
```

---

## Guia para Frontend

### Fluxo Recomendado

**1. Escolher tipo de hospedagem:**

```
[ ] Municipio da VPS Central
[ ] Municipio em VPS Dedicada
```

**2. Se VPS Central:**

a) Buscar municipios disponiveis:
```javascript
const response = await fetch('/mobile/v1/admin/cities/available-for-mobile', {
  headers: { Authorization: 'Bearer TOKEN' }
});
const { cities } = await response.json();
```

b) Exibir dropdown/autocomplete para selecionar

c) Adicionar ao mobile:
```javascript
await fetch('/mobile/v1/admin/cities', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    city_id: selectedCity.id,
    hosting_mode: 'shared',
    mobile_visible: true,
    is_active: true,
    sort_order: 0
  })
});
```

**3. Se VPS Dedicada:**

```javascript
await fetch('/mobile/v1/admin/cities', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    city_name: 'Cliente XYZ',
    city_slug: 'cliente-xyz',
    tenant_code: 'XYZ001',
    hosting_mode: 'dedicated',
    api_base_url: 'https://api.clientexyz.com.br',
    mobile_visible: true,
    is_active: true,
    sort_order: 1
  })
});
```

---

## Exemplo de Formulario

### VPS Central
```
┌─────────────────────────────────────┐
│ Tipo: ● VPS Central                │
├─────────────────────────────────────┤
│ Municipio: [Autocomplete ▼]        │
│   > Sao Paulo (SP)                 │
│   > Rio de Janeiro (RJ)            │
│   > Belo Horizonte (MG)            │
│                                     │
│ [Ao selecionar - Preview]         │
│ Nome: Sao Paulo (automatico)       │
│ Slug: sao-paulo (automatico)       │
│ URL: https://prod... (automatico)  │
│                                     │
│ ☑ Visivel no app mobile            │
│ ☑ Ativo                            │
│ Ordem: [0]                         │
│                                     │
│ [Adicionar ao Mobile]              │
└─────────────────────────────────────┘
```

### VPS Dedicada
```
┌─────────────────────────────────────┐
│ Tipo: ● VPS Dedicada               │
├─────────────────────────────────────┤
│ Nome: [_____________]              │
│ Slug: [_____________]              │
│ Codigo Tenant: [_____________]     │
│ URL da VPS: [____________________] │
│                                     │
│ ☑ Visivel no app mobile            │
│ ☑ Ativo                            │
│ Ordem: [0]                         │
│                                     │
│ [Adicionar ao Mobile]              │
└─────────────────────────────────────┘
```

---

## Variaveis de Ambiente

```bash
# URL da API central para municipios shared
MOBILE_CENTRAL_API_URL=https://prod-api.afirmeplay.com.br
```

---

## Migration

Executar migration para adicionar city_id:

```bash
flask db upgrade
```

Migration: `20260625_add_city_id_to_mobile_directory`
