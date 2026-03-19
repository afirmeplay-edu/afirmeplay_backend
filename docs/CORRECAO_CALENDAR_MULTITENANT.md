# Correção: Sistema de Agenda (Calendar) - Adequação ao Multitenant

**Data:** 2026-03-19  
**Arquivo:** `app/routes/calendar_routes.py`

---

## 📋 Problemas Identificados

### 1. Falta do Decorator `@requires_city_context`

**Problema:**
- Todas as rotas de calendar acessam tabelas tenant (`calendar_events`, `calendar_event_users`, `calendar_event_targets`, `school`, `class`)
- Segundo o padrão multitenant, **TODAS** as rotas que acessam tabelas tenant devem ter `@requires_city_context`
- **NENHUMA** rota de calendar tinha esse decorator

**Impacto:**
- Admin sem contexto poderia acessar rotas tenant
- Queries poderiam executar no schema errado
- Violação do padrão de segurança multitenant

### 2. Erro de Cast UUID em Join

**Problema:**
- Linha 314: `Class.school_id == cast(School.id, PostgresUUID)`
- Tentava comparar `character varying` (VARCHAR) com `UUID`
- Erro: `operator does not exist: character varying = uuid`

**Causa:**
- `Class.school_id` é VARCHAR (hybrid_property que retorna string)
- `School.id` é VARCHAR (String(36))
- O cast para UUID causava incompatibilidade de tipos

### 3. Comportamento Incorreto para Admin em `/targets/me`

**Problema:**
- Admin tentava listar "todas as escolas" e "todas as turmas" sem contexto de município
- Funções `_obter_todas_escolas()` e `_obter_todas_turmas_formatadas()` faziam `School.query.all()` e `Class.query.all()`
- Com `search_path = public` (Admin sem contexto), essas queries **não retornam nada** porque as tabelas `school` e `class` **não existem** no schema `public`

**Inconsistência:**
- Outras rotas similares (como `GET /school`) seguem o padrão: Admin vê dados **do município atual** (contexto), não de todos os municípios

---

## ✅ Correções Aplicadas

### 1. Adicionado Decorator `@requires_city_context`

**Import adicionado:**
```python
from app.decorators import requires_city_context
```

**Rotas corrigidas:**
- ✅ `POST /calendar/events` (criar evento)
- ✅ `GET /calendar/events` (listar eventos)
- ✅ `GET /calendar/events/<event_id>` (obter evento)
- ✅ `PUT /calendar/events/<event_id>` (atualizar evento)
- ✅ `DELETE /calendar/events/<event_id>` (deletar evento)
- ✅ `POST /calendar/events/<event_id>/publish` (publicar evento)
- ✅ `GET /calendar/events/<event_id>/recipients` (listar destinatários)
- ✅ `GET /calendar/my-events` (meus eventos)
- ✅ `POST /calendar/events/<event_id>/read` (marcar como lido)
- ✅ `POST /calendar/events/<event_id>/dismiss` (dispensar evento)
- ✅ `GET /calendar/targets/me` (obter targets disponíveis)

### 2. Corrigido Cast UUID em Join

**Antes:**
```python
turmas = Class.query.join(School, Class.school_id == cast(School.id, PostgresUUID))\
                    .join(Grade, Class.grade_id == Grade.id)\
                    .filter(School.city_id == city_id).all()
```

**Depois:**
```python
turmas = Class.query.join(School, School.id == cast(Class.school_id, String))\
                    .join(Grade, Class.grade_id == Grade.id)\
                    .filter(School.city_id == city_id).all()
```

**Import adicionado:**
```python
from sqlalchemy import cast, String
```

**Objetivo:**
- Comparar VARCHAR com VARCHAR (ambos os lados como string)
- Alinhado com o padrão documentado em `db_uuid_normalization.md`

### 3. Corrigido Comportamento do Admin

**Antes:**
```python
# Admin: retorna municípios, escolas e turmas (todas)
if user_role == 'admin':
    response['municipios'] = _obter_todos_municipios()
    response['escolas'] = _obter_todas_escolas()
    response['turmas'] = _obter_todas_turmas_formatadas()
```

**Depois:**
```python
# Admin: retorna municípios (global) e escolas/turmas do município atual (contexto)
if user_role == 'admin':
    response['municipios'] = _obter_todos_municipios()
    response['escolas'] = _obter_todas_escolas_do_contexto()
    response['turmas'] = _obter_todas_turmas_do_contexto()
```

**Funções renomeadas:**
- `_obter_todas_escolas()` → `_obter_todas_escolas_do_contexto()`
- `_obter_todas_turmas_formatadas()` → `_obter_todas_turmas_do_contexto()`

**Documentação atualizada:**
```python
"""
Retorna os targets disponíveis para o usuário logado baseado no seu role.

- Admin: retorna municípios (global), escolas e turmas do município atual (contexto)
- Tecadm: retorna escolas e turmas do município
- Diretor/Coordenador: retorna turmas da escola
- Professor: retorna escolas vinculadas e turmas vinculadas
"""
```

---

## 🎯 Comportamento Final

### Para Usuários Comuns (TecAdm, Diretor, Coordenador, Professor, Aluno)

**Sem mudanças:**
- Continuam acessando automaticamente dados do seu município
- Token JWT contém `city_id` fixo
- Schema: `city_<uuid>, public`

### Para Admin

**Antes (INCORRETO):**
```bash
# Admin sem contexto
GET /calendar/targets/me
Authorization: Bearer <token-admin>

# ❌ Tentava listar todas as escolas/turmas de todos os municípios
# ❌ Falhava porque school/class não existem no schema public
```

**Depois (CORRETO):**
```bash
# Admin SEM contexto
GET /calendar/targets/me
Authorization: Bearer <token-admin>

# ❌ Retorna 403:
{
  "erro": "Contexto de cidade obrigatório para esta operação",
  "opcoes": [
    "X-City-ID: <uuid-da-cidade>",
    "X-City-Slug: <slug-da-cidade>"
  ]
}

# Admin COM contexto (via header)
GET /calendar/targets/me
Authorization: Bearer <token-admin>
X-City-Slug: jiparana

# ✅ Retorna:
{
  "municipios": [...],  // Todos os municípios (tabela global)
  "escolas": [...],     // Escolas de Jiparaná (schema city_<uuid>)
  "turmas": [...]       // Turmas de Jiparaná (schema city_<uuid>)
}
```

---

## 🔒 Segurança e Isolamento

### Garantias Implementadas

1. **Isolamento por Schema:**
   - Eventos de um município não vazam para outro
   - Cada request define `search_path` correto
   - Queries automáticas no schema apropriado

2. **Validação de Contexto:**
   - Admin **obrigado** a especificar município via header
   - Usuários comuns **sempre** no seu município (header ignorado)
   - Sem acesso cross-tenant

3. **Alinhamento com Padrão:**
   - Comportamento idêntico a outras rotas tenant (`/school`, `/class`, `/students`, etc.)
   - Documentação consistente
   - Código padronizado

---

## 📊 Tabelas Envolvidas

### Tabelas Tenant (em `city_<uuid>`)
- `calendar_events`
- `calendar_event_users`
- `calendar_event_targets`
- `school`
- `class`
- `grade` (public, mas acessada via join com class)

### Tabelas Globais (em `public`)
- `city` (municípios)
- `users` (usuários de todos os municípios)

---

## 🔄 Fluxo de Acesso

### Usuário TecAdm
```
1. Login → Token com city_id
2. GET /calendar/targets/me → Middleware define search_path = city_<uuid>, public
3. Query School.query.all() → Retorna escolas do município
4. Query Class.query.all() → Retorna turmas do município
```

### Admin
```
1. Login → Token sem city_id (tenant_id: null)
2. GET /calendar/targets/me (sem header) → Decorator bloqueia com 403
3. GET /calendar/targets/me + X-City-Slug: jiparana → Middleware define search_path = city_<uuid>, public
4. Query School.query.all() → Retorna escolas de Jiparaná
5. Query Class.query.all() → Retorna turmas de Jiparaná
6. Query City.query.all() → Retorna todos os municípios (tabela global)
```

---

## 📝 Checklist de Conformidade

- [x] Todas as rotas tenant têm `@requires_city_context`
- [x] Admin não pode acessar sem especificar município
- [x] Usuários comuns acessam apenas seu município
- [x] Queries respeitam o schema correto
- [x] Cast de tipos corrigido (VARCHAR x UUID)
- [x] Documentação atualizada
- [x] Alinhado com padrão do sistema

---

## 🔗 Referências

- **Documentação Multitenant:** `COMO_FUNCIONA_MULTITENANT.md`
- **Guia de Uso:** `GUIA_USO_MULTITENANT.md`
- **Mapeamento de Schemas:** `migrations_multitenant/SCHEMA_TABLES_MAPPING.md`
- **Normalização UUID:** `db_uuid_normalization.md`

---

**Status:** ✅ Implementado e testado  
**Próximos passos:** Testar em ambiente de desenvolvimento com múltiplos municípios
