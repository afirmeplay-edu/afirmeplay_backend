# 🐛 CORREÇÃO: AttributeError no Modelo Question

## ❌ **PROBLEMA IDENTIFICADO:**

```
AttributeError: 'Question' object has no attribute 'statement'
```

**Onde ocorreu:**
- Arquivo: `app/services/celery_tasks/physical_test_tasks.py`
- Linha: 144
- Contexto: Geração de formulários físicos (Celery task)

---

## 🔍 **CAUSA RAIZ:**

O código estava tentando acessar atributos que **NÃO EXISTEM** no modelo `Question`:

### **❌ Atributos INCORRETOS (que não existem):**
- `question.statement` ❌
- `question.subject` ❌ (é um relacionamento, não string)

### **✅ Atributos CORRETOS (que existem):**

De acordo com o modelo `Question` (`app/models/question.py`):

```python
class Question(db.Model):
    id = db.Column(db.String, primary_key=True)
    number = db.Column(db.Integer)
    text = db.Column(db.String)              # ✅ Texto simples
    formatted_text = db.Column(db.Text)      # ✅ Texto HTML
    title = db.Column(db.String)             # ✅ Título
    command = db.Column(db.String)           # ✅ Comando
    secondstatement = db.Column(db.String)   # ✅ Segunda declaração
    alternatives = db.Column(db.JSON)        # ✅ Alternativas
    correct_answer = db.Column(db.String)    # ✅ Resposta correta
    
    # Relacionamento (não é string direta)
    subject = db.relationship('Subject', backref='questions')  # ❌ Não usar diretamente
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'))  # ✅ Usar o ID
```

---

## 🔧 **CORREÇÃO APLICADA:**

### **Arquivo:** `app/services/celery_tasks/physical_test_tasks.py`

### **Antes (ERRADO):**

```python
questions_data.append({
    'id': str(question.id),
    'statement': question.statement,  # ❌ NÃO EXISTE
    'subject': question.subject,      # ❌ É um relacionamento, não string
    'correct_answer': question.correct_answer,
    'order': tq.order
})
```

### **Depois (CORRETO):**

```python
questions_data.append({
    'id': str(question.id),
    'text': question.text,                    # ✅ Texto simples
    'formatted_text': question.formatted_text, # ✅ Texto formatado
    'title': question.title,                   # ✅ Título
    'alternatives': question.alternatives or [], # ✅ Alternativas
    'correct_answer': question.correct_answer,
    'order': tq.order
})
```

---

## 📊 **ESTRUTURA CORRETA DO MODELO QUESTION:**

### **Campos de Texto da Questão:**

| Campo | Tipo | Descrição | Uso |
|-------|------|-----------|-----|
| `text` | String | Texto simples da questão | ✅ Exibição em PDF/texto puro |
| `formatted_text` | Text (HTML) | Texto formatado com HTML | ✅ Exibição web/rich content |
| `title` | String | Título da questão | ✅ Identificação |
| `command` | String | Comando da questão | ✅ Enunciado específico |
| `secondstatement` | String | Segunda declaração | ✅ Texto adicional |

### **Outros Campos Importantes:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `alternatives` | JSON | Array de alternativas (A, B, C, D, E) |
| `correct_answer` | String | Resposta correta (ex: "A") |
| `number` | Integer | Número da questão |
| `value` | Float | Valor/peso da questão |
| `question_type` | String | Tipo (multipleChoice, essay, etc) |

### **Relacionamentos (NÃO usar diretamente como string):**

| Campo | Tipo | Como acessar |
|-------|------|--------------|
| `subject` | Relationship | `question.subject.name` ou `question.subject_id` |
| `grade` | Relationship | `question.grade.name` ou `question.grade_level` |

---

## 🎯 **POR QUE O ERRO OCORREU AGORA?**

Este erro **NÃO é novo**, provavelmente existia desde a criação do arquivo `physical_test_tasks.py`, mas:

1. **O código nunca foi executado até agora**, ou
2. **Foi criado copiando de outro lugar** que tinha estrutura diferente, ou
3. **O modelo Question mudou** e o Celery task não foi atualizado

---

## ✅ **COMO PREVENIR NO FUTURO:**

### **1. Sempre verificar o modelo antes de usar:**

```python
# ✅ BOM: Verificar modelo primeiro
from app.models.question import Question
# Olhar os campos disponíveis no modelo

# ❌ MAU: Assumir que campos existem
question.statement  # Pode não existir!
```

### **2. Usar o mesmo padrão do código existente:**

```python
# Ver como outros lugares usam Question:
# app/services/physical_test_form_service.py (linha 282-287)
{
    'id': question.id,
    'title': question.title,
    'text': question.text,
    'formatted_text': question.formatted_text,
    'secondstatement': question.secondstatement,
    'alternatives': question.alternatives or [],
    'correct_answer': question.correct_answer
}
```

### **3. Testar localmente antes de fazer deploy:**

```bash
# Executar Celery localmente
celery -A app.report_analysis.celery_app worker --loglevel=info

# Testar a task
from app.services.celery_tasks.physical_test_tasks import generate_physical_forms_async
result = generate_physical_forms_async.delay(test_id='...')
```

---

## 🧪 **TESTE APÓS CORREÇÃO:**

### **1. Reiniciar Celery Worker:**

```bash
# No seu terminal/servidor onde o Celery está rodando
# Parar o worker (Ctrl+C)
# Reiniciar:
celery -A app.report_analysis.celery_app worker --loglevel=info
```

**Ou no Docker:**
```bash
docker-compose restart celery_worker
```

### **2. Testar geração de formulários:**

```bash
POST /physical-tests/test/<test_id>/generate-forms
Authorization: Bearer <token>
```

### **3. Verificar logs:**

**Esperado (sucesso):**
```
[CELERY] 🚀 Iniciando geração de formulários físicos...
[CELERY] ✅ Prova encontrada: NOME DA PROVA
[CELERY] 📊 Prova aplicada em X turma(s)
[CELERY] 📝 Total de questões: Y
[CELERY] 📋 Criando gabarito para test_id=...
[CELERY] ✅ Formulários gerados com sucesso! Total: Z
```

**Antes (erro):**
```
[CELERY] ❌ Erro ao gerar formulários físicos: 'Question' object has no attribute 'statement'
```

---

## 📋 **CHECKLIST DE VERIFICAÇÃO:**

- [x] Identificado o problema (atributo inexistente)
- [x] Corrigido `question.statement` → `question.text` + `question.formatted_text`
- [x] Removido acesso direto a `question.subject`
- [x] Adicionados campos corretos (`title`, `alternatives`)
- [x] Documentação criada
- [ ] **PENDENTE:** Reiniciar Celery worker
- [ ] **PENDENTE:** Testar geração de formulários

---

## 🔄 **ARQUIVOS AFETADOS:**

### **Modificado:**
- `app/services/celery_tasks/physical_test_tasks.py` (linhas 140-148)

### **Referência (modelo correto):**
- `app/models/question.py`
- `app/services/physical_test_form_service.py` (exemplo de uso correto)

---

## 💡 **CAMPOS DO MODELO QUESTION (REFERÊNCIA RÁPIDA):**

```python
# ✅ TEXTO/CONTEÚDO
question.text              # String: texto simples
question.formatted_text    # Text: HTML formatado
question.title             # String: título
question.command           # String: comando
question.secondstatement   # String: declaração adicional

# ✅ RESPOSTA
question.alternatives      # JSON: array de alternativas
question.correct_answer    # String: resposta correta (ex: "A")

# ✅ METADADOS
question.number            # Integer: número da questão
question.value             # Float: peso/valor
question.question_type     # String: tipo de questão
question.difficulty_level  # String: nível de dificuldade

# ✅ RELACIONAMENTOS (usar com cuidado)
question.subject_id        # String: ID da disciplina (✅ OK)
question.subject           # Relationship: objeto Subject (❌ não usar diretamente como string)
question.subject.name      # String: nome da disciplina (✅ OK se subject não for None)

# ✅ IMAGENS
question.images            # JSON: array de imagens

# ✅ AUDITORIA
question.created_by        # String: ID do criador
question.created_at        # Timestamp: data de criação
question.updated_at        # Timestamp: última atualização
```

---

## 🚀 **PRÓXIMOS PASSOS:**

1. **REINICIE o Celery worker** para carregar o código corrigido
2. **Teste a geração de formulários** físicos
3. **Verifique os logs** para confirmar que não há mais erros
4. **Confirme que os PDFs** são gerados corretamente

---

## ✅ **CORREÇÃO APLICADA COM SUCESSO!**

O erro foi corrigido. Agora o código usa os campos corretos do modelo `Question`:
- ✅ `text` em vez de `statement`
- ✅ `formatted_text` para conteúdo HTML
- ✅ `title` para identificação
- ✅ `alternatives` para as opções

**Reinicie o Celery worker e teste novamente!** 🚀
