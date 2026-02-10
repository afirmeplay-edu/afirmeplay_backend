# 🏗️ Como Funciona o Sistema Multi-Tenant

## 📋 Visão Geral

O backend agora resolve **automaticamente** qual schema PostgreSQL usar em cada request, baseado em 3 fontes:

1. **Token JWT** (city_id do usuário)
2. **Headers HTTP** (X-City-ID ou X-City-Slug - apenas para admin)
3. **Subdomínio** (slug.afirmeplay.com.br)

Cada município possui seu próprio **schema isolado** no PostgreSQL:

- Schema: `city_<uuid>`
- Exemplo: `city_a1b2c3d4-...`

---

## 🔐 Tipos de Usuário

### 1. Usuário Comum (Aluno, Professor, Coordenador, Diretor, TecAdm)

**Características:**

- Possui `city_id` fixo (obrigatório)
- Só acessa dados do seu município
- Headers X-City-\* são **ignorados** (segurança)

**Fluxo:**

```
1. Login → Token com tenant_id
2. Qualquer request → Middleware usa city_id do token
3. Schema definido: city_<uuid>, public
4. Queries automáticas no schema correto
```

**Exemplo:**

```json
// Response do login
{
  "token": "eyJ...",
  "user": {
    "id": "uuid-123",
    "name": "Prof. João",
    "role": "professor",
    "tenant_id": "city-abc-123",
    "city_slug": "jiparana"
  }
}

// Qualquer request depois
GET /school
Authorization: Bearer <token>
→ Lista escolas de Jiparaná automaticamente
```

---

### 2. Usuário Admin

**Características:**

- **NÃO** possui city_id fixo (`tenant_id: null`)
- Pode acessar **qualquer** município
- Precisa especificar contexto para rotas tenant

#### 2.A) Admin SEM Contexto de Cidade

**Schema usado:** `public` (apenas)

**Pode acessar:**

- ✅ `/city` - Gerenciar cidades
- ✅ Rotas globais

**NÃO pode acessar:**

- ❌ `/school` - Escolas (tenant)
- ❌ `/students` - Alunos (tenant)
- ❌ `/class` - Turmas (tenant)
- ❌ Qualquer rota que exige contexto

**Resposta ao tentar:**

```json
{
	"erro": "Contexto de cidade obrigatório para esta operação",
	"mensagem": "Esta rota exige que você especifique um município...",
	"opcoes": ["X-City-ID: <uuid-da-cidade>", "X-City-Slug: <slug-da-cidade>"]
}
```

#### 2.B) Admin COM Contexto de Cidade

**Schema usado:** `city_<uuid>, public`

**Especificar via:**

1. Header `X-City-ID: <uuid>`
2. Header `X-City-Slug: <slug>`
3. Subdomínio `<slug>.afirmeplay.com.br`

**Pode acessar:**

- ✅ Todas as rotas tenant do município escolhido
- ✅ Todas as rotas globais

---

## 🔄 Fluxo de Resolução de Schema

```
┌─────────────────────────────────────────────────────────┐
│                    REQUEST RECEBIDO                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │  1. Extrair Token JWT       │
         │     - user_id               │
         │     - tenant_id             │
         │     - role                  │
         └──────────┬──────────────────┘
                    │
                    ▼
         ┌─────────────────────────────┐
         │  2. Identificar Tipo        │
         │     Admin ou Comum?         │
         └──────────┬──────────────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
   ┌──────────┐      ┌──────────────┐
   │  COMUM   │      │    ADMIN     │
   └────┬─────┘      └──────┬───────┘
        │                   │
        │              ┌────┴────────────────┐
        │              │                     │
        │              ▼                     ▼
        │      ┌──────────────┐    ┌──────────────┐
        │      │ Tem Header   │    │ Sem Header   │
        │      │ X-City-*?    │    │ X-City-*?    │
        │      └──────┬───────┘    └──────┬───────┘
        │             │                   │
        │             ▼                   ▼
        │    ┌──────────────┐    ┌──────────────┐
        │    │ Resolver     │    │ Verificar    │
        │    │ city_id      │    │ Subdomínio   │
        │    │ do header    │    └──────┬───────┘
        │    └──────┬───────┘           │
        │           │              ┌────┴────┐
        │           │              │         │
        ▼           ▼              ▼         ▼
   ┌─────────────────────────────────────────────┐
   │         3. Definir search_path               │
   │                                               │
   │  • Comum:   city_<tenant_id>, public         │
   │  • Admin:   city_<escolhido>, public         │
   │  • Admin:   public (sem contexto)            │
   └──────────────────┬──────────────────────────┘
                      │
                      ▼
          ┌────────────────────────┐
          │  4. Executar Query     │
          │     Automática no      │
          │     Schema Correto     │
          └────────────────────────┘
```

---

## 🎯 Ordem de Prioridade

Quando há múltiplas fontes de contexto:

```
1º → Token JWT city_id (usuário comum)
      └─ SEMPRE usado se existir
      └─ Headers são IGNORADOS

2º → Header X-City-ID (admin)
      └─ UUID direto da cidade

3º → Header X-City-Slug (admin)
      └─ Resolve slug → city_id

4º → Subdomínio do Host (admin)
      └─ Extrai slug da URL
      └─ Resolve slug → city_id

5º → Fallback public (admin sem contexto)
      └─ Apenas rotas globais
```

**Exemplo de Prioridade:**

```bash
# Admin acessa via subdomínio MAS fornece header diferente
GET https://jiparana.afirmeplay.com.br/school
Headers:
  Authorization: Bearer <token-admin>
  X-City-Slug: portovelho

Resultado: Lista escolas de PORTO VELHO
(Header tem prioridade sobre subdomínio)
```

---

## 🔒 Segurança

### Isolamento Garantido

1. **Usuário Comum:**

    ```python
    # Middleware ignora headers para não-admin
    if user_role != "admin":
        city_id = token_city_id  # Força usar token
        # Headers X-City-* são ignorados
    ```

2. **Validação de Cidade:**

    ```python
    # Toda cidade é validada em public.city
    city = City.query.filter_by(slug=slug).first()
    if not city:
        return 404  # Município não encontrado
    ```

3. **Schema por Request:**
    ```python
    # SET search_path executado em cada request
    # Resetado ao final (teardown_appcontext)
    # Sem estado global
    ```

---

## 📊 Exemplos Práticos

### Exemplo 1: Professor Acessa Suas Escolas

```python
# 1. Login
POST /login
{
  "email": "prof@escola.com",
  "password": "senha123"
}

Response:
{
  "token": "eyJ...",
  "user": {
    "tenant_id": "city-abc-123",
    "city_slug": "jiparana"
  }
}

# 2. Listar escolas (automático)
GET /school
Authorization: Bearer <token>

→ search_path = city_abc-123, public
→ SELECT * FROM schools;
→ Retorna apenas escolas de Jiparaná
```

### Exemplo 2: Admin Lista Todas as Cidades

```python
# 1. Login
POST /login
{
  "email": "admin@sistema.com",
  "password": "admin123"
}

Response:
{
  "token": "eyJ...",
  "user": {
    "tenant_id": null,  # Admin não tem cidade fixa
    "role": "admin"
  }
}

# 2. Listar cidades (rota global)
GET /city
Authorization: Bearer <token>

→ search_path = public
→ SELECT * FROM city;
→ Retorna todas as cidades
```

### Exemplo 3: Admin Acessa Escolas de Jiparaná

```python
# Admin precisa especificar contexto
GET /school
Authorization: Bearer <token-admin>
X-City-Slug: jiparana

→ Resolve slug → city_id
→ search_path = city_abc-123, public
→ SELECT * FROM schools;
→ Retorna escolas de Jiparaná
```

### Exemplo 4: Admin Tenta Acessar Sem Contexto

```python
GET /school
Authorization: Bearer <token-admin>
# Sem headers X-City-*

Response (403):
{
  "erro": "Contexto de cidade obrigatório",
  "opcoes": [
    "X-City-ID: <uuid>",
    "X-City-Slug: <slug>"
  ]
}
```

---

## 🗺️ Subdomínios

### Configuração

Cada município pode ter seu subdomínio:

```
jiparana.afirmeplay.com.br  → Jiparaná
portovelho.afirmeplay.com.br → Porto Velho
ariquemes.afirmeplay.com.br  → Ariquemes
```

### Resolução Automática

```python
# Middleware extrai slug do Host header
Host: jiparana.afirmeplay.com.br

# Busca em public.city.slug
city = City.query.filter_by(slug='jiparana').first()

# Define schema
search_path = f"city_{city.id}, public"
```

### Hosts Ignorados

Não são considerados subdomínios:

- `afirmeplay.com.br`
- `www.afirmeplay.com.br`
- `api.afirmeplay.com.br`
- `files.afirmeplay.com.br`
- `localhost`
- `127.0.0.1`

---

## 🏗️ Estrutura do Banco

### Schema `public`

Tabelas **globais** (compartilhadas):

```sql
public.city         -- Municípios
public.users        -- Usuários de todos os municípios
```

### Schema `city_<uuid>`

Tabelas **tenant** (isoladas por município):

```sql
city_abc123.schools              -- Escolas
city_abc123.students             -- Alunos
city_abc123.classes              -- Turmas
city_abc123.tests                -- Avaliações
city_abc123.evaluation_results   -- Resultados
-- etc...
```

### Como Funciona a Query

```python
# Usuário comum ou admin com contexto
search_path = "city_abc123, public"

# Query ORM automática
schools = School.query.all()

# SQL gerado:
# SELECT * FROM schools;
# PostgreSQL busca primeiro em city_abc123.schools
# Se não existir, busca em public.schools

# Resultado: Apenas escolas de city_abc123
```

---

## 🎨 Decorator @requires_city_context

### O Que Faz

Bloqueia acesso a rotas tenant se não houver contexto de cidade.

### Uso

```python
from app.decorators import requires_city_context

@bp.route('/school', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor")
@requires_city_context  # ← Bloqueia admin sem contexto
def listar_escolas():
    schools = School.query.all()
    return jsonify([...])
```

### Comportamento

**Usuário Comum:**

- ✅ Sempre tem contexto (city_id obrigatório)
- ✅ Passa na validação

**Admin COM contexto:**

- ✅ Forneceu X-City-ID/Slug ou subdomínio
- ✅ Passa na validação

**Admin SEM contexto:**

- ❌ Não forneceu contexto
- ❌ Retorna 403 com instruções

---

## 📝 Resumo

| Aspecto                | Usuário Comum        | Admin                |
| ---------------------- | -------------------- | -------------------- |
| **city_id**            | Obrigatório          | null                 |
| **Pode trocar cidade** | ❌ Não               | ✅ Sim (via headers) |
| **Headers X-City-\***  | Ignorado             | Respeitado           |
| **Rotas globais**      | Depende da permissão | ✅ Sempre            |
| **Rotas tenant**       | ✅ Sua cidade        | Precisa contexto     |
| **Schema padrão**      | `city_<id>, public`  | `public`             |
| **Subdomínio**         | Ignora               | Usa se sem header    |

---

## 🚀 Benefícios

1. **Isolamento Total**: Dados nunca vazam entre municípios
2. **Transparente**: Código existente funciona sem alterações
3. **Performático**: search_path é nativo do PostgreSQL
4. **Seguro**: Multi-camadas de validação
5. **Flexível**: Admin pode acessar qualquer município

---

## 🔧 Logs e Debug

O middleware registra automaticamente:

```python
INFO - Request: GET /school
       User: professor
       Schema: city_abc-123
       City: abc-123

INFO - Request: GET /school
       User: admin
       Schema: city_xyz-456
       City: xyz-456

WARNING - Admin tentou acessar rota tenant sem contexto
```

Para debug:

```python
from app.decorators import get_current_tenant_context

context = get_current_tenant_context()
print(f"City: {context.city_id}")
print(f"Schema: {context.schema}")
print(f"Slug: {context.city_slug}")
```

---

**Implementado em:** 2026-02-10  
**Documentação completa:** Ver arquivos ANALISE_SISTEMA_MULTITENANT.md e GUIA_USO_MULTITENANT.md
