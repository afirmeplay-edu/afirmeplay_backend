# Padrões de Uso da Tabela `class` - Detalhamento

## 📊 Estatísticas de Uso

- **Arquivos que usam Class**: 59 arquivos
- **Uso de `class_id`**: 800+ ocorrências
- **Uso de `school_id`**: 1086+ ocorrências
- **Queries com `.get()`**: Múltiplas ocorrências
- **Queries com `.filter()`**: Centenas de ocorrências
- **Queries com `.filter_by()`**: Dezenas de ocorrências

## 🔍 Padrões de Uso Encontrados

### 1. Criação de Turmas

**Arquivo**: `app/routes/class_routes.py`
```python
# Linha 567-571
new_class = Class(
    name=data["name"],
    school_id=data["school_id"],  # String do JSON
    grade_id=data.get("grade_id")  # UUID (já funciona)
)
```

**Impacto**: `school_id` vem como string do JSON, precisa converter para UUID

### 2. Busca por ID

**Arquivo**: `app/routes/class_routes.py`
```python
# Linha 340
Class.id == class_id  # class_id vem da URL como string

# Linha 323
@bp.route('/<string:class_id>', methods=['GET'])
def get_class(class_id):  # String da URL
    Class.query.filter(Class.id == class_id)
```

**Impacto**: Parâmetros de URL são strings, precisam converter para UUID

### 3. Filtros com `.in_()`

**Padrão mais comum:**
```python
# Múltiplas turmas
Class.query.filter(Class.id.in_(class_ids)).all()

# Múltiplas escolas
Class.query.filter(Class.school_id.in_(school_ids)).all()

# Combinado
Class.query.filter(
    Class.grade_id.in_(grade_uuids),
    Class.school_id.in_(school_ids),
    Class.id.in_(selected_classes)
).all()
```

**Impacto**: Listas vêm como strings do JSON, precisam converter para UUID

### 4. Filtros com `.filter_by()`

```python
# Filtro por escola e série
Class.query.filter_by(school_id=school_id, grade_id=grade_id).all()

# Filtro por ID
Class.query.filter_by(id=class_id).first()
```

**Impacto**: Valores precisam ser UUID

### 5. Joins com Outras Tabelas

```python
# Join com Student
Student.query.join(Class, Student.class_id == Class.id)

# Join com School
Class.query.join(School, Class.school_id == School.id)

# Join com ClassTest
Class.query.join(ClassTest, Class.id == ClassTest.class_id)
```

**Impacto**: Joins funcionarão automaticamente, mas valores em filtros precisam ser UUID

### 6. Retorno em JSON

**Padrão comum:**
```python
return jsonify({
    "id": class_obj.id,  # Atualmente string
    "school_id": class_obj.school_id,  # Atualmente string
    "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None  # Já converte UUID para string
})
```

**Impacto**: UUID precisa ser convertido para string no retorno JSON

### 7. Uso em Dicionários e Listas

```python
# Extração de IDs
class_ids = [c.id for c in classes]
school_ids = [c.school_id for c in classes]

# Uso em mapas
class_map = {cls.id: cls for cls in classes}

# Comparações
if class_id in class_ids:
    # ...
```

**Impacto**: Comparações e listas precisarão trabalhar com UUID

### 8. Validações e Verificações

```python
# Verificação de existência
if class_obj.school_id != school_id:
    raise ValueError("Turma não pertence à escola")

# Verificação de pertencimento
if str(class_obj.grade_id) not in [str(g) for g in selected_grades]:
    raise ValueError("Turma não pertence às séries selecionadas")
```

**Impacto**: Comparações precisarão converter para UUID ou comparar UUIDs diretamente

## 🎯 Casos Especiais

### 1. Formulários Socioeconômicos
- `selectedClasses`: Lista de strings do JSON
- `selectedSchools`: Lista de strings do JSON
- Armazenado em coluna JSON no banco
- **Impacto**: Conversão na entrada e saída

### 2. Filtros de Permissões
- `filter_classes_by_user()`: Filtra turmas por permissões
- Usa `Class.id.in_(teacher_class_ids)`
- **Impacto**: `teacher_class_ids` vem de `TeacherClass.class_id` (precisa converter)

### 3. Relatórios e Dashboards
- Múltiplas queries agregadas
- Filtros complexos com múltiplos `.in_()`
- **Impacto**: Todos os valores precisam ser UUID

### 4. Criação de Testes/Avaliações
- Vincula testes a turmas via `ClassTest`
- `ClassTest.class_id` precisa ser UUID
- **Impacto**: Conversão ao criar vínculos

## ⚠️ Pontos de Atenção

1. **URL Parameters**: Sempre strings, precisam conversão
2. **JSON Payloads**: Sempre strings, precisam conversão
3. **Comparações**: Precisam garantir tipos compatíveis
4. **Listas vazias**: `[]` não precisa conversão
5. **Valores None**: Precisam tratamento especial
6. **Múltiplos `.in_()` juntos**: Podem causar inferência de tipo incorreta

## 🔧 Solução Proposta

### Função Auxiliar Universal
```python
def ensure_uuid(value):
    """Garante que o valor seja UUID, converte string se necessário"""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return value  # Manter se não for UUID válido
    return value

def ensure_uuid_list(values):
    """Garante que lista de valores seja UUIDs"""
    if not values:
        return []
    return [ensure_uuid(v) for v in values]
```

### Uso em Rotas
```python
# Receber do request
class_id = ensure_uuid(request.args.get('class_id'))
class_ids = ensure_uuid_list(data.get('selectedClasses', []))

# Retornar no response
return jsonify({
    "id": str(class_obj.id),  # UUID para string
    "school_id": str(class_obj.school_id) if class_obj.school_id else None
})
```

### Uso em Queries
```python
# Antes
Class.query.filter(Class.id.in_(selected_classes)).all()

# Depois
Class.query.filter(Class.id.in_(ensure_uuid_list(selected_classes))).all()
```

