# Análise: Conversão da Tabela `class` para UUID

## 📋 Resumo Executivo

Esta análise documenta o impacto de converter os campos `id` e `school_id` da tabela `class` de `String` para `UUID` no banco de dados.

## 🔍 Estado Atual

### Modelo Atual (`app/models/studentClass.py`)
```python
class Class(db.Model):
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    school_id = db.Column(db.String, db.ForeignKey('school.id'))
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'))
```

### Campos a Converter
- `class.id`: Atualmente `db.String` → Converter para `UUID(as_uuid=True)`
- `class.school_id`: Atualmente `db.String` → Converter para `UUID(as_uuid=True)`

## 🔗 Tabelas com Foreign Keys para `class.id`

As seguintes tabelas têm `class_id` como foreign key para `class.id`:

1. **`class_test`** (`app/models/classTest.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'))`
   - **Impacto**: Precisa converter para `UUID`

2. **`teacher_class`** (`app/models/teacherClass.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'))`
   - **Impacto**: Precisa converter para `UUID`

3. **`student`** (`app/models/student.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'))`
   - **Impacto**: Precisa converter para `UUID`

4. **`answer_sheet_gabaritos`** (`app/models/answerSheetGabarito.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=True)`
   - **Impacto**: Precisa converter para `UUID`

5. **`student_password_log`** (`app/models/studentPasswordLog.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=True)`
   - **Impacto**: Precisa converter para `UUID`

6. **`calendar_event_user`** (`app/models/calendar_event_user.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=True)`
   - **Impacto**: Precisa converter para `UUID`

7. **`game_classes`** (`app/models/game.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=False)`
   - **Impacto**: Precisa converter para `UUID`

8. **`class_subject`** (`app/models/classSubject.py`)
   - `class_id = db.Column(db.String, db.ForeignKey('class.id'))`
   - **Impacto**: Precisa converter para `UUID`

## 📊 Uso de `class.id` no Código

### 1. Queries com `.in_()` (800+ ocorrências)
**Arquivos principais:**
- `app/routes/test_routes.py` (64 ocorrências)
- `app/routes/evaluation_results_routes.py` (134 ocorrências)
- `app/routes/report_routes.py` (84 ocorrências)
- `app/routes/game_routes.py` (53 ocorrências)
- `app/routes/class_routes.py` (59 ocorrências)
- `app/services/dashboard_service.py` (51 ocorrências)
- `app/permissions/query_filters.py` (15 ocorrências)
- E muitos outros...

**Padrões encontrados:**
```python
# Padrão 1: Filtro direto
Class.query.filter(Class.id.in_(class_ids)).all()

# Padrão 2: Em joins
Student.query.join(Class, Student.class_id == Class.id)

# Padrão 3: Em subqueries
ClassTest.query.filter(ClassTest.class_id.in_(
    Class.query.filter(Class.school_id.in_(school_ids)).with_entities(Class.id)
))
```

### 2. Recebimento em Requests (POST/PUT)
**Arquivos:**
- `app/routes/class_routes.py` - `create_class()`, `update_class()`
- `app/routes/test_routes.py` - criação de testes com turmas
- `app/socioeconomic_forms/routes/socioeconomic_form_routes.py` - `selectedClasses`

**Padrões:**
```python
# Recebido como string do JSON
data = request.get_json()
class_id = data.get("class_id")  # String do frontend
selected_classes = data.get("selectedClasses", [])  # Lista de strings
```

### 3. Retorno em Responses (JSON)
**Arquivos:**
- `app/routes/class_routes.py` - retorna `class.id` e `class.school_id`
- `app/routes/student_routes.py` - retorna `class_id` nos dados do aluno
- `app/socioeconomic_forms/models/form.py` - retorna `selectedClasses` como JSON

**Padrões:**
```python
# Retornado como string
return jsonify({
    "id": class_obj.id,  # String atual
    "school_id": class_obj.school_id  # String atual
})
```

### 4. Comparações e Filtros
**Padrões encontrados:**
```python
# Comparação direta
Class.id == class_id
Class.school_id == school_id

# Filtros com .in_()
Class.id.in_(class_ids)
Class.school_id.in_(school_ids)

# Filtros com .filter_by()
Class.query.filter_by(id=class_id, school_id=school_id)
```

## 📊 Uso de `class.school_id` no Código

### 1. Queries com `.in_()` (1086+ ocorrências)
**Arquivos principais:**
- `app/routes/school_routes.py` (60 ocorrências)
- `app/routes/evaluation_results_routes.py` (70 ocorrências)
- `app/routes/test_routes.py` (58 ocorrências)
- `app/services/dashboard_service.py` (107 ocorrências)
- `app/permissions/query_filters.py` (34 ocorrências)
- E muitos outros...

**Padrões encontrados:**
```python
# Filtro por escola
Class.query.filter(Class.school_id.in_(school_ids)).all()

# Join com School
Class.query.join(School, Class.school_id == School.id)

# Comparação direta
Class.school_id == school_id
```

### 2. Recebimento em Requests
**Arquivos:**
- `app/routes/class_routes.py` - `create_class()`, `update_class()`
- `app/socioeconomic_forms/routes/socioeconomic_form_routes.py` - `selectedSchools`

**Padrões:**
```python
data = request.get_json()
school_id = data.get("school_id")  # String do frontend
selected_schools = data.get("selectedSchools", [])  # Lista de strings
```

## ⚠️ Pontos Críticos de Impacto

### 1. **Foreign Keys em Outras Tabelas**
**8 tabelas** precisam ter seus `class_id` convertidos para UUID:
- `class_test`
- `teacher_class`
- `student`
- `answer_sheet_gabaritos`
- `student_password_log`
- `calendar_event_user`
- `game_classes`
- `class_subject`

### 2. **Serialização JSON**
- Frontend envia/recebe como **strings**
- Backend precisa converter string → UUID ao receber
- Backend precisa converter UUID → string ao retornar

### 3. **Queries com Múltiplos `.in_()`**
- Quando há múltiplos `.in_()` juntos, o SQLAlchemy pode inferir tipos incorretamente
- Especialmente problemático quando há apenas 1 elemento na lista
- **Solução atual**: Usar `==` quando há apenas 1 elemento

### 4. **Comparações Diretas**
- Todas as comparações `Class.id == value` precisarão converter `value` para UUID
- Todas as comparações `Class.school_id == value` precisarão converter `value` para UUID

### 5. **Joins e Relacionamentos**
- Joins como `Student.class_id == Class.id` funcionarão automaticamente
- Mas valores passados como parâmetros precisarão ser UUID

## 📝 Arquivos que Precisarão de Alteração

### Modelos (8 arquivos)
1. `app/models/studentClass.py` - Alterar `id` e `school_id` para UUID
2. `app/models/classTest.py` - Alterar `class_id` para UUID
3. `app/models/teacherClass.py` - Alterar `class_id` para UUID
4. `app/models/student.py` - Alterar `class_id` para UUID
5. `app/models/answerSheetGabarito.py` - Alterar `class_id` para UUID
6. `app/models/studentPasswordLog.py` - Alterar `class_id` para UUID
7. `app/models/calendar_event_user.py` - Alterar `class_id` para UUID
8. `app/models/game.py` - Alterar `class_id` para UUID
9. `app/models/classSubject.py` - Alterar `class_id` para UUID

### Rotas (59 arquivos com uso de Class)
**Principais:**
- `app/routes/class_routes.py` - CRUD de turmas
- `app/routes/test_routes.py` - Criação de testes com turmas
- `app/routes/student_routes.py` - Criação de alunos com turmas
- `app/routes/evaluation_results_routes.py` - Relatórios com turmas
- `app/routes/game_routes.py` - Jogos vinculados a turmas
- `app/socioeconomic_forms/routes/socioeconomic_form_routes.py` - Formulários com turmas
- E muitos outros...

### Serviços (31 arquivos)
**Principais:**
- `app/services/dashboard_service.py`
- `app/services/evaluation_comparison_service.py`
- `app/services/evaluation_aggregator.py`
- `app/permissions/query_filters.py`
- `app/socioeconomic_forms/services/form_service.py`
- `app/socioeconomic_forms/services/distribution_service.py`
- E muitos outros...

## 🔧 Estratégia de Migração Recomendada

### Fase 1: Preparação
1. Criar migração para converter `class.id` de String para UUID
2. Criar migração para converter `class.school_id` de String para UUID
3. Criar migrações para converter todas as foreign keys relacionadas

### Fase 2: Atualização dos Modelos
1. Atualizar `Class` model para usar UUID
2. Atualizar todos os modelos com foreign keys para `class.id`
3. Garantir que defaults gerem UUID corretamente

### Fase 3: Atualização do Código
1. **Conversão na entrada**: Converter strings para UUID ao receber do frontend
2. **Conversão na saída**: Converter UUID para string ao retornar para o frontend
3. **Queries**: Garantir que todos os valores sejam UUID antes de usar em queries

### Fase 4: Testes
1. Testar criação de turmas
2. Testar filtros e queries
3. Testar relacionamentos
4. Testar serialização JSON

## 🎯 Funções Auxiliares Necessárias

```python
def to_uuid(value):
    """Converte string para UUID, mantém UUID se já for UUID"""
    if isinstance(value, str):
        return uuid.UUID(value)
    return value

def to_uuid_list(values):
    """Converte lista de strings para lista de UUIDs"""
    return [to_uuid(v) for v in values]

def uuid_to_str(value):
    """Converte UUID para string para JSON"""
    if value is None:
        return None
    return str(value) if not isinstance(value, str) else value
```

## 📌 Observações Importantes

1. **Frontend não precisa mudar**: Continuará enviando/recebendo strings
2. **Migração de dados**: Precisa converter todos os valores existentes no banco
3. **Compatibilidade**: Garantir que código antigo continue funcionando durante transição
4. **Performance**: UUID pode ter impacto mínimo em performance vs String
5. **Consistência**: `grade_id` já é UUID, então faz sentido `id` e `school_id` também serem

## ✅ Checklist de Verificação

- [ ] Migração de banco de dados criada
- [ ] Modelo `Class` atualizado
- [ ] Modelos com foreign keys atualizados (8 modelos)
- [ ] Rotas de criação/atualização atualizadas
- [ ] Rotas de listagem/filtro atualizadas
- [ ] Serviços atualizados
- [ ] Serialização JSON atualizada
- [ ] Testes atualizados
- [ ] Documentação atualizada

