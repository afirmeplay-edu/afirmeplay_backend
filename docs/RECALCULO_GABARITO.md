# 🔄 Recálculo Automático de Resultados - Correção de Gabarito

## 📋 Visão Geral

Este documento descreve a implementação do sistema de **recálculo automático de resultados** quando um professor corrige o gabarito de uma questão.

### Problema Resolvido

**Cenário Antigo (BUGADO):**

```
1. Professor cria questão com gabarito ERRADO (marca C quando deveria ser A)
2. Aluno faz prova e marca A (resposta correta de fato)
3. Sistema calcula resultado usando gabarito errado (C) → Aluno ERRA ❌
4. Professor corrige gabarito (C → A)
5. ❌ Resultado do aluno NÃO era recalculado
6. ❌ Aluno permanecia com nota errada mesmo tendo acertado
```

**Cenário Novo (CORRIGIDO):**

```
1. Professor cria questão com gabarito ERRADO (marca C quando deveria ser A)
2. Aluno faz prova e marca A (resposta correta de fato)
3. Sistema calcula resultado usando gabarito errado (C) → Aluno ERRA (temporariamente)
4. Professor corrige gabarito (C → A)
5. ✅ Sistema DETECTA a mudança automaticamente
6. ✅ Recalcula TODOS os resultados afetados (síncrono ou assíncrono)
7. ✅ Aluno agora tem nota CORRETA! 🎉
```

---

## 🏗️ Arquitetura da Solução

### Componentes Implementados

#### 1. **Task Celery** (`app/services/celery_tasks/evaluation_recalculation_tasks.py`)

Contém duas funções principais:

##### `recalculate_results_after_answer_correction()` - Task Assíncrona

```python
@celery_app.task(name='evaluation_recalculation_tasks.recalculate_results_after_answer_correction')
def recalculate_results_after_answer_correction(
    question_id: str,
    old_answer: str,
    new_answer: str,
    modified_by: str
) -> Dict[str, Any]
```

**Quando usar:** Quando há **≥ 20 alunos** afetados
**Como funciona:**

- Roda em background via Celery
- Não bloqueia a resposta da API
- Pode processar grandes volumes
- Tem retry automático (até 3 tentativas)
- Timeout: 10 minutos

##### `trigger_recalculation_sync()` - Recálculo Síncrono

```python
def trigger_recalculation_sync(
    question_id: str,
    old_answer: str,
    new_answer: str,
    modified_by: str,
    student_ids: List[str]
) -> Dict[str, Any]
```

**Quando usar:** Quando há **< 20 alunos** afetados
**Como funciona:**

- Executa imediatamente (síncrono)
- Retorna resultado completo na resposta
- Mais rápido para poucos alunos

---

#### 2. **Modificação na Rota PUT** (`app/routes/question_routes.py`)

A rota `PUT /questions/<question_id>` foi modificada para:

1. **Detectar mudança no gabarito:**

    ```python
    old_correct_answer = question.correct_answer
    new_correct_answer = data.get('solution')

    gabarito_changed = (
        new_correct_answer is not None and
        old_correct_answer != new_correct_answer and
        old_correct_answer is not None
    )
    ```

2. **Contar impacto:**

    ```python
    # Buscar provas que usam essa questão
    test_questions = TestQuestion.query.filter_by(question_id=question_id).all()

    # Contar alunos afetados
    student_answers = StudentAnswer.query.filter(...)
    total_students = len(set([sa.student_id for sa in student_answers]))
    ```

3. **Decidir entre síncrono/assíncrono:**

    ```python
    ASYNC_THRESHOLD = 20  # Threshold configurável

    if total_students < ASYNC_THRESHOLD:
        # Recálculo SÍNCRONO
        result = trigger_recalculation_sync(...)
    else:
        # Recálculo ASSÍNCRONO
        task = recalculate_results_after_answer_correction.delay(...)
    ```

---

## 🔧 Configuração

### Registrar Task no Celery

A task foi registrada em `app/report_analysis/celery_app.py`:

```python
celery_app = Celery(
    'report_analysis',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'app.report_analysis.tasks',
        'app.services.celery_tasks.physical_test_tasks',
        'app.services.celery_tasks.answer_sheet_tasks',
        'app.services.celery_tasks.evaluation_recalculation_tasks'  # ✅ NOVA TASK
    ]
)
```

### Threshold Configurável

O threshold de 20 alunos está definido em `question_routes.py`:

```python
ASYNC_THRESHOLD = 20  # A partir de 20 alunos, usar assíncrono
```

**Para alterar o threshold:**

- Edite a constante `ASYNC_THRESHOLD` na função `update_question()`
- Valores sugeridos: 10-50 alunos

---

## 📡 Resposta da API

### Quando NÃO há mudança de gabarito:

```json
{
	"message": "Question updated successfully",
	"question_id": "abc-123",
	"version": 2
}
```

### Quando há mudança de gabarito - Recálculo SÍNCRONO:

```json
{
	"message": "Question updated successfully",
	"question_id": "abc-123",
	"version": 2,
	"gabarito_changed": true,
	"old_answer": "C",
	"new_answer": "A",
	"recalculation": {
		"status": "completed",
		"mode": "sync",
		"tests_affected": 2,
		"students_recalculated": 15,
		"errors": 0
	}
}
```

### Quando há mudança de gabarito - Recálculo ASSÍNCRONO:

```json
{
	"message": "Question updated successfully",
	"question_id": "abc-123",
	"version": 2,
	"gabarito_changed": true,
	"old_answer": "C",
	"new_answer": "A",
	"recalculation": {
		"status": "processing",
		"mode": "async",
		"task_id": "celery-task-uuid",
		"tests_affected": 5,
		"students_to_recalculate": 150,
		"message": "Recálculo em andamento em background"
	}
}
```

### Quando questão não está em nenhuma prova:

```json
{
	"message": "Question updated successfully",
	"question_id": "abc-123",
	"version": 2,
	"gabarito_changed": true,
	"old_answer": "C",
	"new_answer": "A",
	"recalculation": {
		"status": "skipped",
		"reason": "Questão não está em nenhuma prova"
	}
}
```

---

## 🚀 Como Usar

### 1. Usuário Final (Professor)

**Nada muda na interface!** O recálculo é **100% automático e transparente**.

1. Professor edita a questão
2. Altera o campo "Resposta Correta" (ex: de C para A)
3. Salva a questão
4. ✅ Sistema recalcula automaticamente todos os resultados

### 2. Frontend (Desenvolvedor)

**Tratar resposta da API:**

```javascript
// Fazer PUT para atualizar questão
const response = await fetch(`/questions/${questionId}`, {
	method: "PUT",
	body: JSON.stringify(questionData),
});

const result = await response.json();

// Verificar se houve mudança de gabarito
if (result.gabarito_changed) {
	console.log(
		`Gabarito alterado: ${result.old_answer} → ${result.new_answer}`,
	);

	if (result.recalculation.mode === "sync") {
		// Recálculo já concluído
		showNotification(
			`Questão atualizada! ${result.recalculation.students_recalculated} alunos recalculados.`,
		);
	} else if (result.recalculation.mode === "async") {
		// Recálculo em andamento
		showNotification(
			`Questão atualizada! Recalculando ${result.recalculation.students_to_recalculate} alunos...`,
		);
	}
}
```

### 3. Monitorar Task Assíncrona (Opcional)

**Se quiser monitorar o progresso da task:**

```python
from app.report_analysis.celery_app import celery_app

# Obter resultado da task
task_id = "celery-task-uuid"
result = celery_app.AsyncResult(task_id)

print(f"Status: {result.state}")  # PENDING, SUCCESS, FAILURE
print(f"Resultado: {result.result}")
```

---

## 🔍 Logging

O sistema gera logs detalhados em todos os passos:

```
[TASK-abc123] Iniciando recálculo de resultados
  Question ID: question-uuid
  Gabarito: C → A
  Modificado por: user-uuid

[TASK-abc123] 3 prova(s) afetada(s)
[TASK-abc123] Prova test-1: 12 aluno(s) a recalcular
[TASK-abc123] Recalculado: aluno student-1, nova nota: 8.5
[TASK-abc123] Recalculado: aluno student-2, nova nota: 7.2
...

[TASK-abc123] Recálculo concluído
  Provas afetadas: 3
  Alunos recalculados: 35
  Erros: 0
  Duração: 12.45s
```

---

## 🧪 Testando a Implementação

### Teste Manual

1. **Criar questão com gabarito errado:**

    ```
    POST /questions
    {
      "text": "Qual a capital do Brasil?",
      "type": "multipleChoice",
      "options": [
        {"text": "São Paulo", "isCorrect": false},
        {"text": "Brasília", "isCorrect": false},
        {"text": "Rio de Janeiro", "isCorrect": true}  // ❌ ERRADO!
      ],
      "solution": "C"  // ❌ Deveria ser "B"
    }
    ```

2. **Adicionar questão a uma prova**

3. **Alunos fazem a prova:**
    - Aluno 1 marca "B" (correto de fato, mas sistema considera errado)
    - Aluno 2 marca "C" (errado de fato, mas sistema considera certo)

4. **Corrigir gabarito:**

    ```
    PUT /questions/{question_id}
    {
      "solution": "B"  // ✅ CORRIGIDO!
    }
    ```

5. **Verificar resposta:**
    - Se < 20 alunos: recalculation.status = "completed"
    - Se ≥ 20 alunos: recalculation.status = "processing"

6. **Verificar resultados dos alunos:**
    ```
    GET /evaluation-results?test_id={test_id}
    ```

    - Aluno 1 agora deve ter acertado ✅
    - Aluno 2 agora deve ter errado ❌

---

## ⚙️ Detalhes Técnicos

### Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PUT /questions/{id} com novo gabarito                   │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Detectar mudança em correct_answer                       │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Buscar provas que usam essa questão (TestQuestion)      │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Buscar alunos que responderam (StudentAnswer)           │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                        ┌───────┴───────┐
                        │               │
                   < 20 alunos?    ≥ 20 alunos?
                        │               │
            ┌───────────┘               └───────────┐
            ▼                                       ▼
┌───────────────────────┐               ┌───────────────────────┐
│ 5a. Recálculo SÍNCRONO│               │ 5b. Recálculo         │
│ (imediato)            │               │ ASSÍNCRONO (Celery)   │
└───────────┬───────────┘               └───────────┬───────────┘
            │                                       │
            └───────────┬───────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Para cada aluno:                                         │
│    - EvaluationResultService.calculate_and_save_result()    │
│    - Recalcula: nota, proficiência, classificação          │
│    - Atualiza EvaluationResult no banco                    │
└───────────────────────────────┬─────────────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Marcar agregados como dirty (rebuild de relatórios)     │
└─────────────────────────────────────────────────────────────┘
```

### Modelos Envolvidos

```
Question
├── id
├── correct_answer ← CAMPO MONITORADO
└── test_questions (relação)
    │
    └──> TestQuestion (tabela associação)
         ├── test_id
         └── question_id
              │
              └──> Test
                   └── student_answers
                        │
                        └──> StudentAnswer
                             ├── student_id
                             ├── answer
                             └── is_correct ← RECALCULADO
                                  │
                                  └──> EvaluationResult
                                       ├── grade ← ATUALIZADO
                                       ├── proficiency ← ATUALIZADO
                                       └── classification ← ATUALIZADO
```

---

## 🔐 Segurança e Performance

### Segurança

- ✅ Requer autenticação JWT
- ✅ Apenas roles autorizados: admin, professor, coordenador, diretor, tecadm
- ✅ Validação de dados de entrada
- ✅ Tratamento de erros com rollback

### Performance

- ✅ Threshold de 20 alunos para decidir síncrono/assíncrono
- ✅ Recálculo assíncrono não bloqueia a API
- ✅ Timeout configurável (10 min)
- ✅ Retry automático em caso de falha
- ✅ Processamento em lote via Celery

### Otimizações Futuras (Opcional)

- [ ] Cache de resultados intermediários
- [ ] Paralelização do recálculo (processar múltiplas provas em paralelo)
- [ ] Notificação via WebSocket quando recálculo assíncrono concluir
- [ ] Dashboard de monitoramento de tasks

---

## 🐛 Troubleshooting

### Problema: Recálculo não está funcionando

**Verificar:**

1. Celery worker está rodando?

    ```bash
    celery -A app.report_analysis.celery_app worker --loglevel=info
    ```

2. Redis está acessível?

    ```bash
    redis-cli ping  # Deve retornar PONG
    ```

3. Logs do Celery:
    ```bash
    tail -f celery.log
    ```

### Problema: Recálculo está lento

**Soluções:**

- Diminuir o threshold (de 20 para 10 alunos)
- Aumentar workers do Celery
- Otimizar queries do banco (adicionar índices)

### Problema: Alguns alunos não foram recalculados

**Verificar:**

- Logs da task (procurar por `recalculation_errors`)
- Se o aluno tem `EvaluationResult` cadastrado
- Se o aluno tem `StudentAnswer` para a questão

---

## 📊 Métricas e Monitoramento

### Logs Importantes

```python
# Log quando gabarito muda
"🔄 Gabarito alterado para questão {question_id}: {old} → {new}"

# Log de impacto
"📊 Impacto: {tests} provas, {students} alunos"

# Log de modo
"⚡ Recálculo SÍNCRONO ({students} alunos)"
"🚀 Recálculo ASSÍNCRONO ({students} alunos)"

# Log de conclusão
"[TASK-{id}] Recálculo concluído: {tests} provas, {students} alunos, {duration}s"
```

### Métricas Recomendadas (Grafana/Prometheus)

- `question_gabarito_changes_total` - Total de mudanças de gabarito
- `recalculation_sync_total` - Total de recálculos síncronos
- `recalculation_async_total` - Total de recálculos assíncronos
- `recalculation_duration_seconds` - Tempo de execução
- `recalculation_students_total` - Total de alunos recalculados

---

## 📚 Referências

- **Código principal:**
    - `app/services/celery_tasks/evaluation_recalculation_tasks.py`
    - `app/routes/question_routes.py`
    - `app/services/evaluation_result_service.py`

- **Modelos relacionados:**
    - `app/models/question.py`
    - `app/models/testQuestion.py`
    - `app/models/studentAnswer.py`
    - `app/models/evaluationResult.py`

- **Configuração Celery:**
    - `app/report_analysis/celery_app.py`

---

## ✅ Checklist de Implementação

- [x] Task Celery criada
- [x] Task registrada no celery_app.py
- [x] Rota PUT modificada para detectar mudança
- [x] Lógica de decisão síncrono/assíncrono
- [x] Recálculo síncrono implementado
- [x] Recálculo assíncrono implementado
- [x] Logging detalhado
- [x] Tratamento de erros
- [x] Documentação criada
- [ ] Testes unitários (próximo passo)
- [ ] Testes de integração (próximo passo)
- [ ] Notificação no frontend (opcional)

---

**Autor:** Sistema de Recálculo Automático v1.0  
**Data:** 2026-02-04  
**Threshold:** 20 alunos (configurável)
