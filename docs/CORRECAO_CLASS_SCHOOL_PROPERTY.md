# Correção: Class.school como Property vs Relationship

## 📋 Resumo

O model `Class` usa `school` como uma `@property` em vez de um `relationship` do SQLAlchemy para evitar problemas de tipo UUID vs VARCHAR. Isso significa que **não é possível usar `joinedload()` ou `jl()` com `Class.school`**.

## 🔍 Problema

### Erro que aparece:

```
sqlalchemy.exc.ArgumentError: expected ORM mapped attribute for loader strategy argument
```

Ou:

```
sqlalchemy.exc.NoInspectionAvailable: No inspection system is available for object of type <class 'property'>
```

### Causa Raiz

O model `Class` (`app/models/studentClass.py`) define `school` como uma `@property`:

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

**Por que isso foi feito?**
- `Class.school_id` é `VARCHAR(36)` no banco de dados
- `School.id` também é `VARCHAR(36)`
- O SQLAlchemy estava fazendo cast automático de VARCHAR para UUID quando detectava formato UUID válido
- Isso causava erro: `operator does not exist: character varying = uuid`
- A solução foi usar uma `@property` que sempre converte para string antes de fazer a query

## ❌ Código que NÃO funciona

### Exemplo 1: joinedload direto

```python
# ❌ ERRADO - Vai dar erro
from sqlalchemy.orm import joinedload

classes = Class.query.options(
    joinedload(Class.school)  # ❌ Class.school é property, não relationship
).filter(Class.id.in_(class_ids)).all()
```

### Exemplo 2: joinedload encadeado

```python
# ❌ ERRADO - Vai dar erro
from sqlalchemy.orm import joinedload as jl

students = Student.query.options(
    jl(Student.class_),
    jl(Student.class_, Class.school)  # ❌ Class.school é property
).filter(Student.class_id.in_(class_ids)).all()
```

### Exemplo 3: joinedload com múltiplos níveis

```python
# ❌ ERRADO - Vai dar erro
from sqlalchemy.orm import joinedload

query = ClassTest.query.options(
    joinedload(ClassTest.class_).joinedload(Class.grade),
    joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city)  # ❌ Class.school é property
).all()
```

## ✅ Código CORRETO

### Exemplo 1: Remover joinedload de Class.school

```python
# ✅ CORRETO
from sqlalchemy.orm import joinedload

classes = Class.query.filter(Class.id.in_(class_ids)).all()
# A property school será acessada normalmente: class_obj.school
for cls in classes:
    if cls.school:  # ✅ Funciona normalmente
        print(cls.school.name)
```

### Exemplo 2: Remover joinedload encadeado

```python
# ✅ CORRETO
from sqlalchemy.orm import joinedload as jl

students = Student.query.options(
    jl(Student.class_)
    # ✅ Removido: jl(Student.class_, Class.school)
).filter(Student.class_id.in_(class_ids)).all()

# Acessar school normalmente depois
for student in students:
    if student.class_ and student.class_.school:  # ✅ Funciona normalmente
        print(student.class_.school.name)
```

### Exemplo 3: Remover joinedload de Class.school, manter outros

```python
# ✅ CORRETO
from sqlalchemy.orm import joinedload

query = ClassTest.query.options(
    joinedload(ClassTest.class_).joinedload(Class.grade)
    # ✅ Removido: joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city)
).all()

# Acessar school normalmente depois
for ct in query:
    if ct.class_ and ct.class_.school:  # ✅ Funciona normalmente
        if ct.class_.school.city:  # ✅ Funciona normalmente
            print(ct.class_.school.city.name)
```

## 🔧 Como Corrigir

### Passo 1: Identificar o erro

Procure por mensagens de erro como:
- `ArgumentError: expected ORM mapped attribute for loader strategy argument`
- `NoInspectionAvailable: No inspection system is available for object of type <class 'property'>`

### Passo 2: Encontrar o código problemático

Busque no código por:
```bash
# Buscar por joinedload com Class.school
grep -r "joinedload.*Class.school" app/
grep -r "jl(.*Class.school" app/
```

### Passo 3: Remover a referência

**Antes:**
```python
query.options(
    joinedload(Class.school)  # ❌ Remover esta linha
)
```

**Depois:**
```python
query  # ✅ Remover o joinedload de Class.school
```

**Antes:**
```python
query.options(
    jl(Student.class_, Class.school)  # ❌ Remover Class.school desta linha
)
```

**Depois:**
```python
query.options(
    jl(Student.class_)  # ✅ Remover apenas Class.school
)
```

### Passo 4: Acessar school normalmente

A `@property` `Class.school` funciona normalmente quando acessada diretamente:

```python
class_obj = Class.query.first()
if class_obj.school:  # ✅ Funciona normalmente
    print(class_obj.school.name)
```

## 📍 Onde isso pode ocorrer

### Arquivos que já foram corrigidos:

1. ✅ `app/routes/report_routes.py` - 5 ocorrências corrigidas
2. ✅ `app/routes/evaluation_results_routes.py` - 3 ocorrências corrigidas
3. ✅ `app/services/evaluation_filters.py` - 1 ocorrência corrigida

### Padrões comuns onde pode aparecer:

1. **Queries com `joinedload()` ou `jl()`**
   ```python
   Class.query.options(joinedload(Class.school))
   ```

2. **Queries encadeadas**
   ```python
   Student.query.options(jl(Student.class_, Class.school))
   ```

3. **Queries com múltiplos níveis**
   ```python
   ClassTest.query.options(
       joinedload(ClassTest.class_).joinedload(Class.school)
   )
   ```

## 🧪 Teste Rápido

Para verificar se há problemas:

```python
# Teste 1: Verificar se Class.school é property
from app.models.studentClass import Class
import inspect

print(type(Class.school))  # Deve ser <class 'property'>

# Teste 2: Tentar usar joinedload (vai dar erro)
from sqlalchemy.orm import joinedload
try:
    Class.query.options(joinedload(Class.school)).first()
except Exception as e:
    print(f"Erro esperado: {e}")  # Deve dar ArgumentError
```

## 📝 Notas Importantes

1. **Performance**: A `@property` faz uma query manual cada vez que é acessada. Se precisar de performance, considere fazer eager loading manual:

   ```python
   # Buscar classes
   classes = Class.query.filter(Class.id.in_(class_ids)).all()
   
   # Buscar escolas manualmente (uma query só)
   school_ids = [str(cls.school_id) for cls in classes if cls.school_id]
   schools = {s.id: s for s in School.query.filter(School.id.in_(school_ids)).all()}
   
   # Usar o dicionário
   for cls in classes:
       school = schools.get(cls.school_id)
       if school:
           print(school.name)
   ```

2. **Alternativa futura**: Se no futuro `Class.school_id` e `School.id` forem convertidos para UUID no banco, poderemos voltar a usar `relationship` normal.

3. **Outros models**: Este problema é específico de `Class.school`. Outros relationships funcionam normalmente.

## 🔗 Referências

- Model: `app/models/studentClass.py`
- Issue relacionada: Problema de tipo UUID vs VARCHAR em `school_id`
- Solução implementada: `@property` que sempre converte para string

## ✅ Checklist de Correção

- [ ] Identificar o erro `ArgumentError` ou `NoInspectionAvailable`
- [ ] Buscar por `joinedload(Class.school)` ou `jl(..., Class.school)`
- [ ] Remover a referência a `Class.school` do `joinedload()`
- [ ] Manter outros `joinedload()` que não envolvem `Class.school`
- [ ] Testar se o código funciona (acessar `class_obj.school` diretamente)
- [ ] Verificar se não há regressões

---

**Última atualização**: 2026-01-07  
**Versão**: 1.0

