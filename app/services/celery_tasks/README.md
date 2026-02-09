# Celery Tasks - Processamento Assíncrono

Este diretório contém todas as tasks Celery para processamento assíncrono de operações demoradas.

## 📋 **Tasks Disponíveis**

### **1. generate_physical_forms_async**

Gera formulários físicos (PDFs) de forma assíncrona para evitar timeout.

**Arquivo:** `physical_test_tasks.py`

**Uso:**

```python
from app.services.celery_tasks.physical_test_tasks import generate_physical_forms_async

# Disparar task
task = generate_physical_forms_async.delay(
    test_id='abc-123-def',
    force_regenerate=False
)

# Obter task_id para polling
task_id = task.id
```

**Parâmetros:**

- `test_id` (str): ID da prova (UUID)
- `force_regenerate` (bool, opcional): Forçar regeneração mesmo se já existirem formulários

**Retorno:**

```python
{
    'success': bool,
    'test_id': str,
    'test_title': str,
    'generated_forms': int,
    'total_students': int,
    'total_questions': int,
    'gabarito_id': str,
    'forms': List[Dict],  # Lista de formulários gerados
    'message': str
}
```

**Tempo estimado:** 2-10 minutos (dependendo do número de alunos)

**Timeout:** 15 minutos máximo

**Retries:** 2 tentativas automáticas em caso de falha

---

### **2. recalculate_results_after_answer_correction**

Recalcula resultados de avaliações após correção de gabarito.

**Arquivo:** `evaluation_recalculation_tasks.py`

**Uso:**

```python
from app.services.celery_tasks.evaluation_recalculation_tasks import (
    recalculate_results_after_answer_correction,
    trigger_recalculation_sync
)

# Recálculo ASSÍNCRONO (≥ 20 alunos)
task = recalculate_results_after_answer_correction.delay(
    question_id='question-uuid',
    old_answer='C',
    new_answer='A',
    modified_by='user-uuid'
)

# Recálculo SÍNCRONO (< 20 alunos)
result = trigger_recalculation_sync(
    question_id='question-uuid',
    old_answer='C',
    new_answer='A',
    modified_by='user-uuid',
    student_ids=['student-1', 'student-2']
)
```

**Parâmetros:**

- `question_id` (str): ID da questão que teve gabarito corrigido
- `old_answer` (str): Resposta correta antiga (ex: "C")
- `new_answer` (str): Resposta correta nova (ex: "A")
- `modified_by` (str): ID do usuário que fez a alteração

**Retorno:**

```python
{
    'success': bool,
    'task_id': str,
    'question_id': str,
    'old_answer': str,
    'new_answer': str,
    'tests_affected': int,
    'students_recalculated': int,
    'errors': List[Dict],
    'duration_seconds': float
}
```

**Tempo estimado:** 5 segundos a 10 minutos (dependendo do número de alunos)

**Timeout:** 10 minutos máximo

**Retries:** 3 tentativas automáticas em caso de falha

**Threshold:** 20 alunos (< 20 = síncrono, ≥ 20 = assíncrono)

**Quando é disparada:**

- Automaticamente ao atualizar campo `correct_answer` de uma questão
- Via `PUT /questions/{question_id}`
- Sistema detecta mudança e dispara recálculo

**Documentação completa:** `docs/RECALCULO_GABARITO.md`

---

## 🔧 **Como Adicionar Novas Tasks**

### **Passo 1: Criar arquivo da task**

```python
# app/services/celery_tasks/my_new_task.py

from app.report_analysis.celery_app import celery_app
from celery import Task

@celery_app.task(
    bind=True,
    name='my_module.my_task_name',
    max_retries=2,
    default_retry_delay=60,
    time_limit=600,  # 10 minutos
    soft_time_limit=540
)
def my_async_task(self: Task, param1: str, param2: int) -> dict:
    """
    Descrição da task

    Args:
        param1: Descrição do parâmetro 1
        param2: Descrição do parâmetro 2

    Returns:
        Dict com resultado
    """
    try:
        # Sua lógica aqui
        result = do_something(param1, param2)

        return {
            'success': True,
            'data': result
        }

    except Exception as e:
        # Retry automático
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        else:
            return {
                'success': False,
                'error': str(e)
            }
```

### **Passo 2: Registrar no `__init__.py`**

```python
# app/services/celery_tasks/__init__.py

from app.services.celery_tasks.my_new_task import my_async_task

__all__ = [
    'generate_physical_forms_async',
    'my_async_task'  # Adicionar aqui
]
```

### **Passo 3: Registrar no Celery**

```python
# app/report_analysis/celery_app.py

celery_app = Celery(
    'report_analysis',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'app.report_analysis.tasks',
        'app.services.celery_tasks.physical_test_tasks',
        'app.services.celery_tasks.my_new_task'  # Adicionar aqui
    ]
)
```

### **Passo 4: Criar rota de polling (opcional)**

```python
# app/routes/my_routes.py

@bp.route('/task/<string:task_id>/status', methods=['GET'])
@jwt_required()
def get_my_task_status(task_id):
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    return jsonify({
        'status': task.state.lower(),
        'result': task.result if task.ready() else None
    }), 200
```

---

## 📚 **Referências**

- **Celery Documentation:** https://docs.celeryproject.org/
- **Configuração do Celery:** `app/report_analysis/celery_app.py`
- **Tasks de Relatórios:** `app/report_analysis/tasks.py`
- **Worker Manager:** `app/report_analysis/worker_manager.py`

---

## ⚙️ **Configurações Importantes**

### **Timeouts**

- `task_time_limit`: Tempo máximo total (hard limit) - worker é terminado
- `task_soft_time_limit`: Soft limit - exceção SoftTimeLimitExceeded é lançada

### **Retries**

- `max_retries`: Número máximo de tentativas
- `default_retry_delay`: Tempo entre retries (segundos)
- `task_acks_late`: Acknowledge apenas após conclusão (não ao iniciar)

### **Serialização**

- `task_serializer='json'`: Tasks são serializadas em JSON
- `accept_content=['json']`: Aceita apenas JSON
- `result_serializer='json'`: Resultados em JSON

---

## 🚀 **Boas Práticas**

1. **Nome da task:** Use formato `module.task_name` para evitar conflitos
2. **Docstring:** Sempre documente parâmetros e retorno
3. **Try/Catch:** Sempre capture exceções e use retry
4. **Logging:** Use `logger.info()` para acompanhar progresso
5. **Retorno:** Sempre retorne dict com `success` e `error`/`data`
6. **Timeout:** Configure timeout adequado para a operação
7. **Idempotência:** Tasks devem poder ser executadas múltiplas vezes sem efeitos colaterais

---

## 🔍 **Debugging**

### **Ver logs do worker:**

```bash
# No servidor
docker logs celery_worker_production -f
```

### **Verificar tasks na fila:**

```bash
# No container do worker
celery -A app.report_analysis.celery_app inspect active
```

### **Monitorar com Flower (opcional):**

```bash
celery -A app.report_analysis.celery_app flower
# Acesse: http://localhost:5555
```
