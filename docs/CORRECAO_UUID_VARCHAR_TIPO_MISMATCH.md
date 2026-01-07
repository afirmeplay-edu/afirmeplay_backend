# Correção: Erro de Tipo UUID vs VARCHAR

## 📋 Resumo

Este documento descreve o erro `operator does not exist: character varying = uuid` e todas as correções aplicadas para resolver problemas de incompatibilidade de tipos entre UUID e VARCHAR no PostgreSQL.

## 🔍 Erro Principal

### Erro que aparece:

```
psycopg2.errors.UndefinedFunction: operator does not exist: character varying = uuid
LINE 3: WHERE school.id = '56bfd6b8-8465-4331-a13b-06cb06a8516d'::uu...
HINT: No operator matches the given name and argument types. You might need to add explicit type casts.
```

### Causa Raiz

O banco de dados PostgreSQL tem:
- `school.id` como `VARCHAR(36)` (não UUID)
- `class.school_id` como `VARCHAR(36)` (não UUID)
- `student.school_id` como `VARCHAR(36)` (não UUID)

Mas o SQLAlchemy estava tentando comparar/combinar:
- Colunas VARCHAR com objetos UUID do Python
- Isso causa erro porque PostgreSQL não permite comparação direta entre VARCHAR e UUID

## 🔧 Correções Aplicadas

### 1. Correção dos Models

#### Problema
Alguns models estavam definidos com `UUID(as_uuid=True)` quando o banco era `VARCHAR`.

#### Solução
Garantir que todos os models que referenciam `school.id` usem `db.String(36)`:

**Arquivos corrigidos:**
- ✅ `app/models/school.py` - `id = db.Column(db.String(36), ...)`
- ✅ `app/models/studentClass.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/student.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/manager.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/schoolTeacher.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/schoolCourse.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/calendar_event.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/calendar_event_user.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/studentPasswordLog.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/models/answerSheetGabarito.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/play_tv/models.py` - `school_id = db.Column(db.String(36), ...)`
- ✅ `app/socioeconomic_forms/models/form_recipient.py` - `school_id = db.Column(db.String(36), ...)`

**Exemplo:**
```python
# ❌ ERRADO
school_id = db.Column(UUID(as_uuid=True), db.ForeignKey('school.id'))

# ✅ CORRETO
school_id = db.Column(db.String(36), db.ForeignKey('school.id'))
```

### 2. Correção de School.query.get()

#### Problema
`School.query.get()` não faz cast automático e pode quebrar se receber UUID.

#### Solução
Criar função helper `get_school_safe()` e substituir todos os `School.query.get()`:

**Arquivo:** `app/utils/school_helpers.py`
```python
def get_school_safe(school_id):
    """
    Busca escola de forma segura, convertendo UUID para string se necessário.
    
    ✅ CORRETO: School.query.filter(School.id == str(school_id)).first()
    ❌ ERRADO: School.query.get(school_id)  # Não faz cast e quebra
    """
    if school_id is None:
        return None
    
    school_id_str = uuid_to_str(school_id)
    if not school_id_str:
        return None
    
    return School.query.filter(School.id == school_id_str).first()
```

**Arquivos corrigidos:**
- ✅ `app/routes/evaluation_results_routes.py`
- ✅ `app/routes/basic_endpoints.py`
- ✅ `app/routes/student_routes.py`

**Exemplo:**
```python
# ❌ ERRADO
school = School.query.get(class_obj.school_id)

# ✅ CORRETO
from app.utils.school_helpers import get_school_safe
school = get_school_safe(class_obj.school_id)

# OU
school = School.query.filter(School.id == str(class_obj.school_id)).first()
```

### 3. Correção de ClassTest.query.filter_by(test_id=)

#### Problema
`ClassTest.test_id` é `VARCHAR`, mas estava recebendo UUID sem conversão.

#### Solução
Sempre converter `test_id` para string antes de usar em `filter_by()`:

**Arquivos corrigidos:**
- ✅ `app/routes/evaluation_results_routes.py`
- ✅ `app/routes/report_routes.py`

**Exemplo:**
```python
# ❌ ERRADO
class_tests = ClassTest.query.filter_by(test_id=test_id).all()

# ✅ CORRETO
class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
```

### 4. Correção de JSONB com school_id

#### Problema
JSONB precisa de strings, não UUIDs.

#### Solução
Converter `school_id` para string antes de usar em operações JSONB:

**Arquivo:** `app/routes/test_routes_backup.py`

**Exemplo:**
```python
# ❌ ERRADO
filters.append(cast(Test.schools, JSONB).op('@>')([school_id]))

# ✅ CORRETO
school_id_str = str(school_id)
filters.append(cast(Test.schools, JSONB).op('@>')([school_id_str]))
```

### 5. Correção de query_filters.py

#### Problema
Funções de filtro retornavam UUID em vez de string.

#### Solução
Garantir que todas as funções retornem strings:

**Arquivo:** `app/permissions/query_filters.py`

**Exemplo:**
```python
# ❌ ERRADO
def filter_schools_by_user(user):
    school_id = get_manager_school(user['id'])
    return School.query.filter(School.id == school_id).all()

# ✅ CORRETO
def filter_schools_by_user(user):
    from app.utils.uuid_helpers import uuid_to_str
    school_id = get_manager_school(user['id'])
    school_id_str = uuid_to_str(school_id) if school_id else None
    return School.query.filter(School.id == school_id_str).all() if school_id_str else []
```

### 6. Correção de dashboard_service.py

#### Problema
Queries com `Class.school_id` e `Student.school_id` precisavam garantir tipo string.

#### Solução
Usar `uuid_list_to_str()` para converter listas de IDs:

**Arquivo:** `app/services/dashboard_service.py`

**Exemplo:**
```python
# ❌ ERRADO
school_ids = scope.get("school_ids") or []
classes = Class.query.filter(Class.school_id.in_(school_ids)).all()

# ✅ CORRETO
from app.utils.uuid_helpers import uuid_list_to_str
school_ids = scope.get("school_ids") or []
school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
classes = Class.query.filter(Class.school_id.in_(school_ids_str)).all() if school_ids_str else []
```

### 7. Correção de Class.school como Property

#### Problema
O relationship `Class.school` causava erro de tipo durante lazy loading.

#### Solução
Substituir `relationship` por `@property` que sempre converte para string:

**Arquivo:** `app/models/studentClass.py`

**Antes:**
```python
school = db.relationship(
    "School",
    foreign_keys=[school_id],
    primaryjoin="Class.school_id == School.id",
    lazy="select",
    uselist=False,
    back_populates="classes"
)
```

**Depois:**
```python
@property
def school(self):
    """Property que sempre retorna School usando string, evitando problema de tipo UUID vs VARCHAR"""
    from app.models.school import School
    if self._school_id is None:
        return None
    school_id_str = str(self._school_id) if not isinstance(self._school_id, str) else self._school_id
    return School.query.filter(School.id == school_id_str).first()
```

**⚠️ IMPORTANTE:** Isso significa que não é possível usar `joinedload(Class.school)`. Veja [CORRECAO_CLASS_SCHOOL_PROPERTY.md](./CORRECAO_CLASS_SCHOOL_PROPERTY.md) para mais detalhes.

### 8. Correção de permissions/utils.py

#### Problema
Funções retornavam UUID em vez de string.

#### Solução
Garantir que sempre retornem strings:

**Arquivo:** `app/permissions/utils.py`

**Exemplo:**
```python
# ❌ ERRADO
def get_manager_school(user_id):
    manager = Manager.query.filter_by(user_id=user_id).first()
    return manager.school_id  # Pode ser UUID

# ✅ CORRETO
def get_manager_school(user_id):
    manager = Manager.query.filter_by(user_id=user_id).first()
    return str(manager.school_id) if manager and manager.school_id else None
```

## 🛠️ Funções Helper Criadas

### app/utils/uuid_helpers.py

```python
def uuid_to_str(value):
    """Converte UUID para string, mantém string se já for string"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)

def uuid_list_to_str(values):
    """Converte lista de UUIDs/strings para lista de strings"""
    if not values:
        return []
    return [uuid_to_str(v) for v in values if v is not None]
```

### app/utils/school_helpers.py

```python
def get_school_safe(school_id):
    """Busca escola de forma segura, convertendo UUID para string se necessário"""
    if school_id is None:
        return None
    
    school_id_str = uuid_to_str(school_id)
    if not school_id_str:
        return None
    
    return School.query.filter(School.id == school_id_str).first()
```

## 📍 Arquivos Corrigidos

### Models (12 arquivos)
1. ✅ `app/models/school.py`
2. ✅ `app/models/studentClass.py`
3. ✅ `app/models/student.py`
4. ✅ `app/models/manager.py`
5. ✅ `app/models/schoolTeacher.py`
6. ✅ `app/models/schoolCourse.py`
7. ✅ `app/models/calendar_event.py`
8. ✅ `app/models/calendar_event_user.py`
9. ✅ `app/models/studentPasswordLog.py`
10. ✅ `app/models/answerSheetGabarito.py`
11. ✅ `app/play_tv/models.py`
12. ✅ `app/socioeconomic_forms/models/form_recipient.py`

### Routes (5 arquivos)
1. ✅ `app/routes/dashboard_routes.py` - Adicionado rollback
2. ✅ `app/routes/evaluation_results_routes.py` - Corrigido `filter_by(test_id=)` e `School.query.get()`
3. ✅ `app/routes/report_routes.py` - Corrigido `filter_by(test_id=)`
4. ✅ `app/routes/basic_endpoints.py` - Corrigido `School.query.get()`
5. ✅ `app/routes/student_routes.py` - Corrigido `School.query.get()`

### Services (2 arquivos)
1. ✅ `app/services/dashboard_service.py` - Corrigido queries com `school_id`
2. ✅ `app/services/evaluation_filters.py` - Removido `joinedload(Class.school)`

### Permissions (2 arquivos)
1. ✅ `app/permissions/query_filters.py` - Corrigido retorno de strings
2. ✅ `app/permissions/utils.py` - Corrigido retorno de strings

### Utils (2 arquivos criados)
1. ✅ `app/utils/uuid_helpers.py` - Funções helper para conversão
2. ✅ `app/utils/school_helpers.py` - Função `get_school_safe()`

## 🔍 Como Identificar o Problema

### Erro no Log:
```
psycopg2.errors.UndefinedFunction: operator does not exist: character varying = uuid
```

### Buscar no Código:
```bash
# Buscar por School.query.get()
grep -r "School\.query\.get(" app/

# Buscar por filter_by(test_id=) sem str()
grep -r "filter_by(test_id=" app/ | grep -v "str("

# Buscar por UUID(as_uuid=True) em school_id
grep -r "school_id.*UUID(as_uuid=True)" app/models/

# Buscar por joinedload(Class.school)
grep -r "joinedload.*Class\.school" app/
```

## ✅ Checklist de Correção

Quando encontrar o erro `operator does not exist: character varying = uuid`:

- [ ] Verificar se o model está usando `db.String(36)` em vez de `UUID(as_uuid=True)`
- [ ] Substituir `School.query.get()` por `get_school_safe()` ou `filter().first()`
- [ ] Converter `test_id` para string em `ClassTest.query.filter_by(test_id=str(test_id))`
- [ ] Converter `school_id` para string antes de usar em JSONB
- [ ] Garantir que funções de filtro retornem strings
- [ ] Usar `uuid_list_to_str()` em queries com `.in_()`
- [ ] Remover `joinedload(Class.school)` se existir
- [ ] Adicionar `db.session.rollback()` em blocos try-except
- [ ] Testar a rota que estava dando erro

## 📝 Regras de Ouro

1. **Nunca compare UUID com VARCHAR direto**
   - Sempre converta antes da query

2. **School.query.get() é perigoso**
   - Use `get_school_safe()` ou `filter().first()`

3. **filter_by() não faz cast**
   - Sempre use `str()` quando necessário

4. **JSONB sempre string**
   - Converta UUID para string antes de usar

5. **Class.school é property**
   - Não use `joinedload(Class.school)`

## 🔗 Referências Relacionadas

- [CORRECAO_CLASS_SCHOOL_PROPERTY.md](./CORRECAO_CLASS_SCHOOL_PROPERTY.md) - Problema específico com `joinedload(Class.school)`
- `app/utils/uuid_helpers.py` - Funções helper
- `app/utils/school_helpers.py` - Função `get_school_safe()`

---

**Última atualização**: 2026-01-07  
**Versão**: 1.0

