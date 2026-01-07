# Refatoração do Sistema de Permissões

**Autor:** Sistema de Refatoração de Permissões  
**Data:** 2025-01-XX  
**Status:** Concluído

---

## 📋 Sumário

1. [Visão Geral](#visão-geral)
2. [Estrutura Criada](#estrutura-criada)
3. [Migração de Código Antigo](#migração-de-código-antigo)
4. [Como Usar](#como-usar)
5. [Mapeamento de Funcionalidades](#mapeamento-de-funcionalidades)
6. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

Esta refatoração centraliza toda a lógica de permissões da aplicação Flask em um único módulo reutilizável (`app/permissions/`). O objetivo é:

-   ✅ Eliminar código duplicado
-   ✅ Facilitar manutenção e testes
-   ✅ Melhorar consistência de permissões
-   ✅ Centralizar regras de negócio
-   ✅ Manter compatibilidade com código existente

**⚠️ IMPORTANTE:** Nenhum código antigo foi removido - apenas comentado com referências claras à nova localização.

---

## 📁 Estrutura Criada

```
app/permissions/
├── __init__.py          # Exporta todas as funções principais
├── roles.py             # Constantes e utilitários de papéis
├── utils.py             # Funções auxiliares (buscar vínculos)
├── decorators.py        # Decoradores de rota (@role_required)
├── rules.py               # Funções de permissão de alto nível
└── query_filters.py     # Filtros SQLAlchemy aplicáveis a queries
```

---

## 📄 Descrição dos Módulos

### 1. `roles.py` - Constantes e Utilitários

Centraliza todas as definições de roles e utilitários.

```python
from app.permissions.roles import Roles

# Roles disponíveis
Roles.ADMIN      # "admin"
Roles.TECADM     # "tecadm"
Roles.DIRETOR    # "diretor"
Roles.COORDENADOR # "coordenador"
Roles.PROFESSOR  # "professor"
Roles.ALUNO      # "aluno"

# Métodos utilitários
Roles.is_admin_role(user_role)
Roles.has_report_access(user_role)
Roles.can_edit_tests(user_role)
Roles.normalize(role)  # Normaliza role para string lowercase
```

### 2. `utils.py` - Funções Auxiliares

Busca informações de vínculos de usuários.

```python
from app.permissions.utils import (
    get_teacher_schools,      # Lista escolas do professor
    get_manager_school,        # Escola do diretor/coordenador
    get_teacher_classes,        # Turmas do professor
    get_user_scope              # Escopo completo do usuário
)

# Exemplos
school_ids = get_teacher_schools(user_id)
school_id = get_manager_school(user_id)
class_ids = get_teacher_classes(user_id)
scope = get_user_scope(user)
```

### 3. `decorators.py` - Decoradores de Rota

Decorador `@role_required` centralizado.

```python
from app.permissions import role_required

@app.route('/admin/users')
@role_required('admin', 'tecadm')
def list_users():
    # Apenas admin ou tecadm podem acessar
    pass
```

### 4. `rules.py` - Regras de Permissão

Funções de alto nível para verificar permissões.

```python
from app.permissions import (
    can_view_test,
    can_edit_test,
    can_view_school,
    can_view_class,
    get_user_permission_scope
)

# Verificar se usuário pode ver avaliação
if not can_view_test(user, test_id):
    return jsonify({"error": "Acesso negado"}), 403
```

### 5. `query_filters.py` - Filtros SQLAlchemy

Filtra queries SQLAlchemy baseado em permissões.

```python
from app.permissions import filter_schools_by_user

# Filtrar escolas por permissões
query = School.query.with_entities(School.id, School.name)
query = filter_schools_by_user(query, current_user)
escolas = query.all()
```

---

## 🔄 Migração de Código Antigo

### Arquivos Comentados (Não Removidos)

#### 1. `app/decorators/role_required.py`

-   ⚠️ **SUBSTITUÍDO** por `app/permissions/decorators.py`
-   Mantido para compatibilidade de imports
-   Adicione aviso no topo do arquivo

#### 2. Funções em `app/routes/evaluation_results_routes.py`

##### `professor_pode_ver_avaliacao()`

-   ⚠️ **SUBSTITUÍDA** por `app.permissions.rules.can_view_test()`
-   Aceita agora dict completo do usuário
-   Suporta todos os roles (não apenas professor)

##### `professor_pode_ver_avaliacao_turmas()`

-   ⚠️ **SUBSTITUÍDA** por `app.permissions.rules.can_view_test()`

##### `verificar_permissao_filtros()`

-   ⚠️ **SUBSTITUÍDA** por `app.permissions.rules.get_user_permission_scope()`

##### `_gerar_opcoes_proximos_filtros()`

-   ⚠️ **MELHORIA FUTURA** sugerida: usar `app.permissions.query_filters`

---

## 📖 Como Usar

### Importar Funções

```python
# Importar tudo (recomendado)
from app.permissions import (
    role_required,
    can_view_test,
    can_edit_test,
    filter_schools_by_user,
    get_user_permission_scope
)

# OU importar módulos específicos
from app.permissions.decorators import role_required
from app.permissions.rules import can_view_test
from app.permissions.query_filters import filter_schools_by_user
```

### Exemplos de Uso

#### 1. Proteger uma rota com decorador

```python
from app.permissions import role_required

@bp.route('/admin/users')
@jwt_required()
@role_required('admin', 'tecadm')
def list_users():
    # Código da rota
    pass
```

#### 2. Verificar permissão de visualização

```python
from app.permissions import can_view_test

@bp.route('/avaliacoes/<test_id>')
@jwt_required()
@role_required('admin', 'professor', 'coordenador', 'diretor', 'tecadm')
def get_avaliacao(test_id):
    user = get_current_user_from_token()

    if not can_view_test(user, test_id):
        return jsonify({"error": "Acesso negado"}), 403

    # Buscar e retornar avaliação
    test = Test.query.get(test_id)
    return jsonify(test.to_dict()), 200
```

#### 3. Filtrar query por permissões

```python
from app.permissions import filter_schools_by_user

@bp.route('/escolas')
@jwt_required()
@role_required('admin', 'professor', 'coordenador', 'diretor', 'tecadm')
def list_escolas():
    user = get_current_user_from_token()

    # Aplicar filtros automáticos
    query = School.query.with_entities(School.id, School.name)
    query = filter_schools_by_user(query, user)
    escolas = query.all()

    return jsonify(escolas), 200
```

#### 4. Obter escopo de permissões

```python
from app.permissions import get_user_permission_scope

def verificar_acesso(user):
    permissao = get_user_permission_scope(user)

    if not permissao['permitted']:
        return jsonify({"error": permissao['error']}), 403

    # Usar permissao['scope'] para aplicar filtros
    if permissao['scope'] == 'all':
        # Admin: sem filtros
        pass
    elif permissao['scope'] == 'municipio':
        # TECADM: filtrar por município
        city_id = user.get('city_id')
    elif permissao['scope'] == 'escola':
        # Diretor/Coordenador/Professor: filtrar por escola
        pass
```

---

## 🗺️ Mapeamento de Funcionalidades

### Código Antigo → Novo Código

| Função Antiga                                    | Novo Local                         | Função Nova                       |
| ------------------------------------------------ | ---------------------------------- | --------------------------------- |
| `professor_pode_ver_avaliacao(user_id, test_id)` | `app/permissions/rules.py`         | `can_view_test(user, test_id)`    |
| `verificar_permissao_filtros(user)`              | `app/permissions/rules.py`         | `get_user_permission_scope(user)` |
| `@role_required`                                 | `app/permissions/decorators.py`    | `@role_required` (mantido)        |
| Filtros inline em queries                        | `app/permissions/query_filters.py` | `filter_*_by_user(query, user)`   |
| `Teacher.query.filter_by(user_id=...)`           | `app/permissions/utils.py`         | `get_teacher(user_id)`            |
| `SchoolTeacher.query.filter_by(teacher_id=...)`  | `app/permissions/utils.py`         | `get_teacher_schools(user_id)`    |

---

## 💡 Exemplos Práticos

### Exemplo 1: Migrar verificação de permissão de avaliação

**ANTES:**

```python
@bp.route('/avaliacoes/<test_id>')
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_avaliacao(test_id):
    user = get_current_user_from_token()

    # Lógica antiga
    if user['role'] == 'professor':
        if not professor_pode_ver_avaliacao(user['id'], test_id):
            return jsonify({"error": "Acesso negado"}), 403
    elif user['role'] in ['diretor', 'coordenador']:
        manager = Manager.query.filter_by(user_id=user['id']).first()
        # ... mais lógica complexa

    test = Test.query.get(test_id)
    return jsonify(test.to_dict()), 200
```

**DEPOIS:**

```python
from app.permissions import can_view_test

@bp.route('/avaliacoes/<test_id>')
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_avaliacao(test_id):
    user = get_current_user_from_token()

    # Verificação unificada para todos os roles
    if not can_view_test(user, test_id):
        return jsonify({"error": "Acesso negado"}), 403

    test = Test.query.get(test_id)
    return jsonify(test.to_dict()), 200
```

### Exemplo 2: Filtrar lista de escolas

**ANTES:**

```python
@bp.route('/escolas')
def list_escolas():
    user = get_current_user_from_token()

    query = School.query
    if user['role'] == 'professor':
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        school_teachers = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
        school_ids = [st.school_id for st in school_teachers]
        query = query.filter(School.id.in_(school_ids))
    elif user['role'] in ['diretor', 'coordenador']:
        manager = Manager.query.filter_by(user_id=user['id']).first()
        if manager and manager.school_id:
            query = query.filter(School.id == manager.school_id)

    escolas = query.all()
    return jsonify([e.to_dict() for e in escolas]), 200
```

**DEPOIS:**

```python
from app.permissions import filter_schools_by_user

@bp.route('/escolas')
def list_escolas():
    user = get_current_user_from_token()

    query = School.query
    query = filter_schools_by_user(query, user)

    escolas = query.all()
    return jsonify([e.to_dict() for e in escolas]), 200
```

### Exemplo 3: Verificar permissões de filtros

**ANTES:**

```python
def verificar_permissao_filtros(user):
    role = user.get('role')
    if role == 'ADMIN':
        return {'permitted': True, 'scope': 'all', ...}
    elif role == 'TECADM':
        return {'permitted': True, 'scope': 'municipio', ...}
    # ... mais 50 linhas
```

**DEPOIS:**

```python
from app.permissions import get_user_permission_scope

def verificar_permissao_filtros(user):
    return get_user_permission_scope(user)
```

---

## ✅ Checklist de Migração

Para migrar rotas existentes:

-   [ ] Importar funções de `app.permissions`
-   [ ] Substituir verificações inline por `can_view_*()` ou `can_edit_*()`
-   [ ] Substituir filtros de query por `filter_*_by_user()`
-   [ ] Substituir `verificar_permissao_filtros()` por `get_user_permission_scope()`
-   [ ] Testar permissões de cada role
-   [ ] Remover imports antigos (opcional, código ainda funciona)

---

## 🧪 Estrutura de Roles

### ADMIN

-   ✅ Acesso total a todos os recursos
-   ✅ Pode ver todas as escolas, turmas, avaliações
-   ✅ Sem filtros de permissão

### TECADM

-   ✅ Acesso a todos os recursos do município
-   ✅ Filtra por `city_id` automaticamente
-   ❌ Não acessa recursos de outros municípios

### DIRETOR / COORDENADOR

-   ✅ Acesso apenas à sua escola
-   ✅ Via `Manager.school_id`
-   ❌ Não acessa recursos de outras escolas

### PROFESSOR

-   ✅ Acesso às avaliações que criou
-   ✅ Acesso às avaliações aplicadas em suas escolas
-   ✅ Via `SchoolTeacher` e `TeacherClass`
-   ❌ Não acessa avaliações de outras escolas

### ALUNO

-   ❌ Sem acesso a relatórios ou avaliações (exceto próprias)

---

## 📝 Notas Importantes

1. **Compatibilidade:** Código antigo continua funcionando
2. **Nenhuma função foi removida:** Apenas comentada com referências
3. **Migração gradual:** Você pode migrar arquivo por arquivo
4. **Validação:** Sempre teste após migrar rotas
5. **Performance:** Queries podem ser otimizadas usando filtros centralizados

---

## 🔗 Links Relacionados

-   `app/permissions/__init__.py` - Exports principais
-   `app/models/user.py` - RoleEnum (mantido para compatibilidade)
-   `app/decorators/role_required.py` - Código antigo (comentado)

---

**Fim da Documentação**
