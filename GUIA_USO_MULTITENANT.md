# Guia de Uso: Sistema Multi-Tenant com Resolução Automática de Schema

## 🎯 Visão Geral

O sistema agora resolve automaticamente qual schema PostgreSQL usar com base em:

- **Token JWT** (city_id do usuário)
- **Headers HTTP** (`X-City-ID` ou `X-City-Slug` para admin)
- **Subdomínio** (`<slug>.afirmeplay.com.br`)

---

## 🔐 Como Usar nas Rotas

### 1. Rotas Globais (Sem Contexto de Cidade)

Rotas que **NÃO** exigem contexto de cidade:

```python
# app/routes/city_routes.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required

bp = Blueprint('city', __name__, url_prefix='/city')

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin")
# ❌ NÃO USAR @requires_city_context aqui
def listar_cidades():
    """Admin pode listar todas as cidades sem especificar contexto"""
    cities = City.query.all()
    return jsonify([...])
```

### 2. Rotas Tenant (Com Contexto de Cidade)

Rotas que **EXIGEM** contexto de cidade:

```python
# app/routes/school_routes.py
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.decorators import requires_city_context, get_current_tenant_context  # ✅ NOVO

bp = Blueprint('school', __name__, url_prefix='/school')

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador")
@requires_city_context  # ✅ ADICIONAR este decorator
def listar_escolas():
    """
    Lista escolas do município no contexto atual.

    - Usuário comum: lista escolas do seu município
    - Admin: precisa fornecer X-City-ID ou X-City-Slug
    """
    # Opcional: acessar informações do contexto
    context = get_current_tenant_context()

    # Query já filtra automaticamente pelo schema correto
    schools = School.query.all()  # Busca em city_<id>, não em public

    return jsonify([
        {
            "id": school.id,
            "name": school.name,
            "city_id": context.city_id  # Informação do contexto
        }
        for school in schools
    ])
```

### 3. Validação Extra de Acesso

Se sua rota recebe `city_id` como parâmetro:

```python
from app.decorators import requires_city_context, validate_tenant_access

@bp.route('/school/<city_id>/details', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor")
@requires_city_context
def detalhes_escola(city_id):
    """
    Garante que usuário só acessa dados da cidade permitida.
    """
    # Validar se o city_id da URL corresponde ao contexto
    permitido, erro = validate_tenant_access(city_id)
    if not permitido:
        return jsonify({"erro": erro}), 403

    # Continuar com a lógica...
    schools = School.query.filter_by(city_id=city_id).all()
    return jsonify([...])
```

---

## 📡 Testando com cURL

### 1. Login (Usuário Comum)

```bash
# Professor fazendo login
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "registration": "prof123",
    "password": "senha123"
  }'

# Resposta:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid-user",
    "name": "Prof. João",
    "role": "professor",
    "tenant_id": "uuid-city-123",
    "city_slug": "jiparana"  // ✅ NOVO
  }
}
```

### 2. Acessar Rota Tenant (Usuário Comum)

```bash
# Listar escolas do professor
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token>"

# ✅ Lista automaticamente escolas de city_uuid-123
# Schema usado: city_uuid-123, public
```

### 3. Admin sem Contexto (Rota Global)

```bash
# Admin fazendo login
curl -X POST http://localhost:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@sistema.com",
    "password": "admin123"
  }'

# Resposta:
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid-admin",
    "name": "Administrador",
    "role": "admin",
    "tenant_id": null,        // Admin não tem cidade fixa
    "city_slug": null
  }
}

# Listar todas as cidades (rota global)
curl http://localhost:5000/city \
  -H "Authorization: Bearer <token-admin>"

# ✅ Funciona! Schema: public
```

### 4. Admin Tentando Rota Tenant sem Contexto

```bash
# Admin tentando listar escolas sem especificar cidade
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token-admin>"

# ❌ Erro 403:
{
  "erro": "Contexto de cidade obrigatório para esta operação",
  "mensagem": "Esta rota exige que você especifique um município...",
  "opcoes": [
    "X-City-ID: <uuid-da-cidade>",
    "X-City-Slug: <slug-da-cidade>"
  ],
  "alternativa": "Ou acesse via subdomínio: <slug>.afirmeplay.com.br"
}
```

### 5. Admin com Header X-City-Slug

```bash
# Admin especificando cidade via slug
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token-admin>" \
  -H "X-City-Slug: jiparana"

# ✅ Lista escolas de Jiparaná
# Schema usado: city_<id-jiparana>, public
```

### 6. Admin com Header X-City-ID

```bash
# Admin especificando cidade via UUID
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token-admin>" \
  -H "X-City-ID: uuid-city-123"

# ✅ Lista escolas da cidade uuid-city-123
# Schema usado: city_uuid-city-123, public
```

### 7. Acesso via Subdomínio

```bash
# Acessar via subdomínio (resolve automaticamente)
curl https://jiparana.afirmeplay.com.br/school \
  -H "Authorization: Bearer <token-admin>"

# ✅ Lista escolas de Jiparaná
# Slug 'jiparana' é extraído do Host
```

### 8. Prioridade: Header > Subdomínio

```bash
# Header tem prioridade sobre subdomínio
curl https://jiparana.afirmeplay.com.br/school \
  -H "Authorization: Bearer <token-admin>" \
  -H "X-City-Slug: portovelho"

# ✅ Lista escolas de Porto Velho (não Jiparaná)
# Header X-City-Slug sobrescreve subdomínio
```

---

## 🔍 Verificando o Schema Atual

### No Código

```python
from app.decorators import get_current_tenant_context

@bp.route('/debug/context', methods=['GET'])
@jwt_required()
def debug_context():
    context = get_current_tenant_context()

    return jsonify({
        "city_id": context.city_id,
        "city_slug": context.city_slug,
        "schema": context.schema,
        "user_role": context.user_role,
        "is_admin": context.is_admin,
        "has_tenant_context": context.has_tenant_context
    })
```

### No Banco de Dados

```sql
-- Verificar search_path ativo
SHOW search_path;
-- Resultado: city_uuid-123, public

-- Verificar qual schema está sendo usado
SELECT current_schema();
-- Resultado: city_uuid-123
```

---

## 📋 Checklist: Adicionar Decorator nas Rotas

### Rotas que PRECISAM de `@requires_city_context`:

- [x] `/school` (todas)
- [x] `/students` (todas)
- [x] `/class` (todas)
- [x] `/test` (todas)
- [x] `/evaluations` (todas)
- [x] `/reports` (todas)
- [x] `/dashboard` (todas)
- [x] `/physical-test` (todas)
- [x] `/answer-sheets` (todas)
- [x] `/certificates` (todas)
- [x] `/socioeconomic-forms` (todas)
- [x] `/plantao-online` (todas)
- [x] `/play-tv` (todas)
- [x] `/calendar` (todas) - Corrigido em 2026-03-19

### Rotas que NÃO precisam:

- [ ] `/city` (gerenciar cidades - global)
- [ ] `/login`, `/logout` (autenticação - global)
- [ ] `/` (documentação - global)
- [ ] `/swagger.yaml` (spec - global)

---

## ⚠️ Casos de Erro

### 1. Município Não Encontrado

```bash
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token-admin>" \
  -H "X-City-Slug: cidade-inexistente"

# Resposta 404:
{
  "erro": "Município não encontrado para o slug: cidade-inexistente"
}
```

### 2. Usuário Comum Tentando Trocar Cidade

```bash
# Professor tentando acessar outra cidade via header
curl http://localhost:5000/school \
  -H "Authorization: Bearer <token-professor>" \
  -H "X-City-Slug: outra-cidade"

# ✅ Header é IGNORADO para usuário comum
# Lista escolas do município do professor (segurança)
```

### 3. TecAdm Tentando Acessar Rota Global

```bash
# TecAdm tentando listar todas as cidades
curl http://localhost:5000/city \
  -H "Authorization: Bearer <token-tecadm>"

# ❌ Erro 403:
{
  "erro": "Acesso negado."
}
# TecAdm não tem permissão para gerenciar cidades
```

---

## 🚀 Deploy em Produção

### 1. Configurar DNS para Subdomínios

```
# Adicionar registros DNS wildcard:
*.afirmeplay.com.br  →  IP do servidor

# Ou registros específicos:
jiparana.afirmeplay.com.br      →  IP
portovelho.afirmeplay.com.br    →  IP
```

### 2. Configurar SSL para Subdomínios

```bash
# Certbot com wildcard
sudo certbot certonly --manual \
  --preferred-challenges=dns \
  -d afirmeplay.com.br \
  -d *.afirmeplay.com.br
```

### 3. Atualizar CORS

```python
# Em .env de produção
FRONTEND_URL=https://innovplay.online

# CORS já aceita subdomínios via regex
# origins: [os.getenv('FRONTEND_URL')]
```

### 4. Popular Slugs no Banco

```sql
-- Ajustar slugs manualmente conforme necessário
UPDATE public.city SET slug = 'jiparana' WHERE name = 'Ji-Paraná';
UPDATE public.city SET slug = 'portovelho' WHERE name = 'Porto Velho';
UPDATE public.city SET slug = 'ariquemes' WHERE name = 'Ariquemes';
-- etc...

-- Verificar duplicatas
SELECT slug, COUNT(*)
FROM public.city
GROUP BY slug
HAVING COUNT(*) > 1;
```

---

## 📊 Monitoramento

### Logs de Resolução

O middleware já registra logs automáticos:

```
INFO - Request: GET /school | User: professor | Schema: city_uuid-123 | City: uuid-123
INFO - Request: GET /school | User: admin | Schema: city_uuid-456 | City: uuid-456
WARNING - Admin tentou acessar rota tenant sem contexto: listar_escolas
ERROR - Usuário comum sem city_id tentou acessar rota tenant
```

### Métricas Recomendadas

```python
# Adicionar em app/__init__.py
@app.before_request
def log_tenant_resolution():
    context = g.get('tenant_context')
    app.logger.info(
        f"Tenant: {context.schema if context else 'none'} | "
        f"Route: {request.path} | "
        f"Method: {request.method}"
    )
```

---

## 🎓 Boas Práticas

### ✅ Fazer

1. **Sempre usar `@requires_city_context` em rotas tenant**

```python
@bp.route('/schools')
@jwt_required()
@requires_city_context  # ← Sempre adicionar
def listar_escolas():
    pass
```

2. **Validar city_id de parâmetros URL**

```python
@bp.route('/school/<city_id>')
@requires_city_context
def detalhes(city_id):
    permitido, erro = validate_tenant_access(city_id)
    if not permitido:
        return jsonify({"erro": erro}), 403
```

3. **Usar contexto para logs e auditoria**

```python
context = get_current_tenant_context()
logger.info(f"Escola criada | city: {context.city_id}")
```

### ❌ Evitar

1. **Não confiar apenas em filtros manuais**

```python
# ❌ Perigoso: fácil esquecer
School.query.filter_by(city_id=user.city_id).all()

# ✅ Seguro: search_path automático
School.query.all()  # Já filtra pelo schema
```

2. **Não misturar lógica de tenant em models**

```python
# ❌ Não fazer isso
class School(db.Model):
    def get_all_for_city(city_id):
        pass

# ✅ Deixar o middleware resolver
```

3. **Não acessar `g.tenant_context` diretamente**

```python
# ❌ Evitar
context = g.tenant_context

# ✅ Usar helper
context = get_current_tenant_context()
```

---

## 🐛 Troubleshooting

### Erro: "Contexto de tenant não encontrado"

**Causa:** Middleware não foi executado  
**Solução:** Verificar se `@app.before_request` está registrado em `create_app()`

### Erro: "Município não encontrado"

**Causa:** Slug inválido ou não existe no banco  
**Solução:**

```sql
SELECT * FROM public.city WHERE slug = 'slug-tentado';
```

### Queries retornando dados errados

**Causa:** Schema incorreto  
**Verificação:**

```python
from sqlalchemy import text
result = db.session.execute(text("SHOW search_path")).scalar()
print(f"Schema atual: {result}")
```

### Admin não consegue alternar cidades

**Causa:** Headers não estão sendo aceitos pelo CORS  
**Solução:** Verificar se `X-City-ID` e `X-City-Slug` estão em `allow_headers`

---

**Documentação completa:** [ANALISE_SISTEMA_MULTITENANT.md](ANALISE_SISTEMA_MULTITENANT.md)
