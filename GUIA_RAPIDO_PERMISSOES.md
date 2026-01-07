# 🚀 Guia Rápido de Permissões

**Refatoração concluída com sucesso!**

---

## ⚡ Início Rápido

### Importar tudo de uma vez:

```python
from app.permissions import (
    role_required,           # Decorador para rotas
    can_view_test,           # Verificar acesso a avaliação
    can_edit_test,            # Verificar edição de avaliação
    can_view_school,          # Verificar acesso a escola
    can_view_class,           # Verificar acesso a turma
    filter_schools_by_user,   # Filtrar escolas por usuário
    filter_classes_by_user,   # Filtrar turmas por usuário
    filter_tests_by_user,     # Filtrar avaliações por usuário
    filter_students_by_user,  # Filtrar estudantes por usuário
    get_user_permission_scope # Obter escopo de permissões
)
```

---

## 📝 3 Padrões de Uso Comuns

### 1️⃣ Decorador de Rota

```python
@bp.route('/admin/users')
@jwt_required()
@role_required('admin', 'tecadm')  # ← Apenas estes roles
def list_users():
    pass
```

### 2️⃣ Verificação de Acesso

```python
if not can_view_test(user, test_id):
    return jsonify({"error": "Acesso negado"}), 403
```

### 3️⃣ Filtrar Query

```python
query = School.query
query = filter_schools_by_user(query, user)  # ← Filtro automático
escolas = query.all()
```

---

## 🗂️ Arquivos Criados

```
app/permissions/
├── __init__.py       → Exports
├── roles.py          → Constantes (Roles.ADMIN, etc)
├── utils.py          → get_teacher_schools(), etc
├── decorators.py     → @role_required
├── rules.py          → can_view_test(), etc
└── query_filters.py  → filter_schools_by_user(), etc
```

---

## ⚠️ Código Antigo

**NENHUM código foi removido!** Apenas comentado.

-   ✅ `app/decorators/role_required.py` - Comentado
-   ✅ Funções em `evaluation_results_routes.py` - Comentadas

Todos têm referências claras para o novo local.

---

## 📚 Documentação Completa

Ver: `REFATORACAO_PERMISSOES.md`

---

## ✅ Status

✅ Estrutura criada  
✅ Funções implementadas  
✅ Código antigo comentado  
✅ Documentação criada  
✅ Zero erros de lint  
✅ Pronto para uso!

---

**🎉 Refatoração concluída com sucesso!**
