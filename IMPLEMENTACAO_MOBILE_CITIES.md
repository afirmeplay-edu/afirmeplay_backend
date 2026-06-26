# Implementação - API Admin Mobile Cities

**Data:** 25/06/2026
**Status:** ✅ Concluído

---

## 📋 Resumo das Alterações

Implementação completa do sistema para adicionar municípios ao catálogo mobile com dois fluxos distintos:

1. **VPS Central (shared)** - Municípios existentes em public.city
2. **VPS Dedicada (dedicated)** - Clientes com infraestrutura própria

---

## ✅ Arquivos Criados

### 1. Migration

- **Arquivo:** `migrations/versions/20260625_add_city_id_to_mobile_directory.py`
- **Descrição:** Adiciona coluna `city_id` (nullable) ao `MobileCityDirectory`
- **Ação:** Executar `flask db upgrade`

### 2. Documentação

- **Arquivo:** `app/routes/mobile/README_ADMIN_API.md`
- **Descrição:** Documentação completa da API com exemplos e fluxos

---

## ✅ Arquivos Modificados

### 1. Modelo

- **Arquivo:** `app/models/mobile_city_directory.py`
- **Alteração:** Adicionado campo `city_id` opcional

### 2. Rotas Admin

- **Arquivo:** `app/routes/mobile/admin_routes.py`
- **Alterações:**
    - Refatoração completa do POST para suportar dois modos
    - Novo endpoint: `GET /admin/cities/available-for-mobile`
    - Geração automática de `tenant_code`
    - Validação inteligente por modo
    - Simplificação do PUT (apenas campos editáveis)

### 3. Documentação

- **Arquivo:** `app/mobile/MOBILE_TENANT_DISCOVERY.md`
- **Alterações:** Atualizado com novos fluxos e endpoints

### 4. Variáveis de Ambiente

- **Arquivo:** `app/.env`
- **Alteração:** Adicionado `MOBILE_CENTRAL_API_URL`

---

## 🔧 Funcionalidades Implementadas

### 1. Listar Municípios Disponíveis

```
GET /mobile/v1/admin/cities/available-for-mobile
```

- Retorna municípios da VPS central que ainda NÃO estão no mobile
- Previne duplicação
- Útil para autocomplete no frontend

### 2. Adicionar Município - Modo Shared

```json
POST /mobile/v1/admin/cities
{
  "city_id": "abc-123-def",
  "hosting_mode": "shared"
}
```

**Automático:**

- Busca município em `public.city`
- Preenche `city_name`, `city_slug`
- Gera `tenant_code` (8 primeiros chars do city_id)
- Define `api_base_url` como URL central

### 3. Adicionar Município - Modo Dedicated

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

**Manual:** Admin fornece todos os dados

### 4. Validações Implementadas

#### Modo Shared:

- ✅ Valida que município existe em `public.city`
- ✅ Valida que município NÃO está no catálogo mobile
- ✅ Gera `tenant_code` automaticamente
- ✅ Define URL central automaticamente

#### Modo Dedicated:

- ✅ Valida formato de URL
- ✅ Valida que URL não é a central
- ✅ Valida unicidade de slug e tenant_code
- ✅ Todos os campos obrigatórios

### 5. Serialização Atualizada

```json
{
	"id": "uuid-catalog",
	"city_id": "abc-123-def", // Novo campo (null para dedicated)
	"city_name": "São Paulo",
	"city_slug": "sao-paulo",
	"tenant_code": "ABC123DE",
	"api_base_url": "https://prod-api.afirmeplay.com.br",
	"hosting_mode": "shared",
	"mobile_visible": true,
	"is_active": true,
	"sort_order": 0,
	"created_at": "2026-06-25T17:00:00Z",
	"updated_at": "2026-06-25T17:00:00Z"
}
```

---

## 🎯 Próximos Passos (Para o Frontend)

### 1. Executar Migration

```bash
flask db upgrade
```

### 2. Implementar Formulário

#### Passo 1: Escolher Tipo

```
○ Município da VPS Central
○ Município em VPS Dedicada
```

#### Passo 2a: Se VPS Central

1. Chamar `GET /admin/cities/available-for-mobile`
2. Exibir dropdown/autocomplete
3. Ao selecionar, mostrar preview dos dados
4. Chamar POST com `city_id` e `hosting_mode: "shared"`

#### Passo 2b: Se VPS Dedicada

1. Exibir formulário com campos manuais
2. Validar no frontend
3. Chamar POST com todos os dados

---

## 📊 Comparação: Antes vs Depois

### Antes

```json
// Admin precisava fornecer TUDO manualmente
POST /mobile/v1/admin/cities
{
  "city_name": "São Paulo",
  "city_slug": "sao-paulo",
  "tenant_code": "SP001",          // Digitado manualmente (repetitivo)
  "api_base_url": "https://prod-api.afirmeplay.com.br",  // Digitado 50x
  "hosting_mode": "shared"
}
```

**Problemas:**

- ❌ Repetitivo para múltiplos municípios
- ❌ Propenso a erros de digitação
- ❌ Sem referência ao município original
- ❌ Risco de duplicação

### Depois

```json
// Admin fornece apenas o essencial
POST /mobile/v1/admin/cities
{
  "city_id": "abc-123-def",        // Selecionado do dropdown
  "hosting_mode": "shared"
}
```

**Benefícios:**

- ✅ 90% menos digitação
- ✅ Dados sempre corretos (copiados da fonte)
- ✅ Referência mantida (city_id)
- ✅ Previne duplicação
- ✅ tenant_code gerado automaticamente

---

## 🔍 Detalhes Técnicos

### Geração de tenant_code

```python
def _generate_tenant_code(city_id: str) -> str:
    """Gera tenant_code a partir do city_id."""
    return city_id.replace("-", "")[:8].upper()
    # Exemplo: "abc-123-def-456" -> "ABC123DE"
```

### Query para Municípios Disponíveis

```sql
SELECT * FROM public.city
WHERE id NOT IN (
  SELECT city_id FROM mobile_city_directory
  WHERE city_id IS NOT NULL
)
ORDER BY name
```

### Estrutura do Banco

```
mobile_city_directory
├── id (PK)
├── city_id (FK opcional) -> public.city.id
├── city_name
├── city_slug (unique)
├── tenant_code (unique)
├── api_base_url
├── hosting_mode (shared|dedicated)
├── mobile_visible
├── is_active
└── sort_order
```

---

## 🚀 Testes Sugeridos

### 1. Adicionar Município Shared

```bash
# 1. Listar disponíveis
GET /mobile/v1/admin/cities/available-for-mobile

# 2. Adicionar ao mobile
POST /mobile/v1/admin/cities
{
  "city_id": "uuid-de-um-municipio",
  "hosting_mode": "shared"
}

# 3. Verificar se foi adicionado
GET /mobile/v1/admin/cities

# 4. Verificar que sumiu da lista de disponíveis
GET /mobile/v1/admin/cities/available-for-mobile
```

### 2. Adicionar Município Dedicated

```bash
POST /mobile/v1/admin/cities
{
  "city_name": "Teste Cliente",
  "city_slug": "teste-cliente",
  "tenant_code": "TEST001",
  "hosting_mode": "dedicated",
  "api_base_url": "https://api.teste.com"
}
```

### 3. Validações

```bash
# Tentar adicionar município já no catálogo (deve retornar 409)
POST /mobile/v1/admin/cities
{
  "city_id": "mesmo-id-de-antes",
  "hosting_mode": "shared"
}

# Tentar usar URL central em modo dedicated (deve retornar 400)
POST /mobile/v1/admin/cities
{
  "city_name": "Test",
  "city_slug": "test",
  "tenant_code": "TEST",
  "hosting_mode": "dedicated",
  "api_base_url": "https://prod-api.afirmeplay.com.br"
}
```

---

## 📚 Documentação

- **API Completa:** `app/routes/mobile/README_ADMIN_API.md`
- **Fluxo Mobile:** `app/mobile/MOBILE_TENANT_DISCOVERY.md`
- **Variáveis:** `.env` -> `MOBILE_CENTRAL_API_URL`

---

## ✅ Checklist de Implementação

- [x] Migration criada
- [x] Modelo atualizado
- [x] Rotas refatoradas
- [x] Endpoint de listagem criado
- [x] Validações implementadas
- [x] Geração automática de tenant_code
- [x] Documentação atualizada
- [x] Zero erros de linter
- [x] Logs de auditoria
- [x] Tratamento de erros

---

**Implementação completa e pronta para uso!** 🎉
