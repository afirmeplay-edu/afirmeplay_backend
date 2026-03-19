# 🔴 PROBLEMA: Celery Travado Após Geração - Chord Callback Não Executa

**Data:** 2026-03-19  
**Status:** 🔴 IDENTIFICADO - Aguardando correção

---

## 🔍 Sintomas Observados

### Logs do Celery:

```
[2026-03-19 20:24:17] Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] received (×4)
[2026-03-19 20:24:19] [GENERATOR ARCH4] Gerando cartões para turma C com overlay
[2026-03-19 20:24:19] [GENERATOR ARCH4] Gerando cartões para turma B com overlay
[2026-03-19 20:24:19] [GENERATOR ARCH4] Gerando cartões para turma A com overlay
[2026-03-19 20:24:19] [GENERATOR ARCH4] Gerando cartões para turma A com overlay
[2026-03-19 20:25:22] [GENERATOR ARCH4] ✅ 11 PDFs gerados para turma C
[2026-03-19 20:25:22] Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 64.55s
[2026-03-19 20:25:23] [GENERATOR ARCH4] ✅ 12 PDFs gerados para turma B
[2026-03-19 20:25:23] Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 65.22s
[2026-03-19 20:25:23] [GENERATOR ARCH4] ✅ 17 PDFs gerados para turma A
[2026-03-19 20:25:23] Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 65.36s
[2026-03-19 20:25:25] [GENERATOR ARCH4] ✅ 22 PDFs gerados para turma A
[2026-03-19 20:25:25] Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 67.27s
```

**Depois disso:** Celery fica **PARADO**, sem executar nada mais!

### Comportamento do Frontend:

- Rota `/answer-sheets/jobs/{job_id}/status` **continua sendo chamada** (polling)
- Job **nunca muda para "completed"**
- Usuário fica esperando indefinidamente

---

## 🎯 Causa Raiz Identificada

### Arquitetura Atual (Chord):

```python
# app/routes/answer_sheet_routes.py (linha 592-605)

# 1. Criar 1 task por turma (group)
header = group(
    generate_answer_sheets_single_class_async.s(class_id=cid, **common_kw)
    for cid in class_ids
)

# 2. Criar chord: group + callback
chord_sig = chord(header)(
    build_zip_and_upload_answer_sheets.s(
        batch_id=job_id,
        base_output_dir=base_output_dir,
        city_id=city_id_scope,
        gabarito_ids=[existing_gabarito_id],
        scope=scope_type,
        num_questions=gabarito.num_questions,
    )
)
```

### O Que Acontece:

1. ✅ **Group tasks executam com sucesso** (4 turmas, 62 alunos)
2. ❌ **Callback `build_zip_and_upload_answer_sheets` NÃO É CHAMADO**
3. ❌ Job fica **travado em "processing"**
4. ❌ PDFs ficam **no diretório temporário** (não são zipados nem enviados ao MinIO)
5. ❌ Celery fica **ocioso** (não processa novas tasks)

---

## 🔬 Análise Técnica

### Chord no Celery:

Um **chord** é composto por:
1. **Header (group):** Múltiplas tasks executadas em paralelo
2. **Body (callback):** Task executada **APÓS** todas as tasks do header terminarem

**Problema conhecido:** Chords podem **travar** se:
- Backend de resultados não está configurado corretamente
- Tasks do header não retornam resultados serializáveis
- Celery worker não está configurado para processar callbacks

### Configuração Atual:

```python
# app/celery_app.py (provável)
result_backend = 'redis://...'  # Necessário para chords
task_track_started = True       # Necessário para chords
```

**Se `result_backend` não estiver configurado ou não funcionar, o chord trava!**

---

## 📊 Evidências do Problema

### 1. Tasks Individuais Terminam com Sucesso:

```
✅ Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 64.55s
✅ Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 65.22s
✅ Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 65.36s
✅ Task answer_sheet_tasks.generate_answer_sheets_single_class_async[...] succeeded in 67.27s
```

### 2. Callback Nunca Aparece nos Logs:

**Esperado:**
```
[CELERY-CHORD] ZIP criado: 12345678 bytes, 62 alunos
[CELERY-CHORD] Upload para MinIO concluído: https://...
```

**Real:**
```
(nada - callback não executou)
```

### 3. Job Fica em "processing":

```python
# app/routes/answer_sheet_routes.py (linha 3323-3325)
job_status = "processing"
if completed == len(task_ids) and task_ids:
    job_status = "completed"
```

**Problema:** `task_ids` contém apenas o **chord ID**, não as tasks individuais!

---

## 🚨 Impactos

### Para o Usuário:

1. ❌ PDFs gerados **não ficam disponíveis** (não são zipados nem enviados ao MinIO)
2. ❌ Job **nunca completa** (fica em "processing" indefinidamente)
3. ❌ Frontend **continua fazendo polling** (desperdiça recursos)
4. ❌ Usuário **não consegue baixar os cartões** gerados

### Para o Sistema:

1. ❌ Celery **fica ocioso** (não processa novas tasks)
2. ❌ Diretórios temporários **acumulam** (não são limpos)
3. ❌ Recursos **desperdiçados** (PDFs gerados mas inacessíveis)

---

## ✅ Soluções Possíveis

### Solução 1: Verificar Configuração do Celery (RÁPIDO)

**Verificar:**
1. `result_backend` está configurado?
2. Redis está acessível?
3. `task_track_started = True`?

**Como testar:**
```python
# No terminal Python
from app.report_analysis.celery_app import celery_app
print(celery_app.conf.result_backend)  # Deve retornar URL do Redis
print(celery_app.conf.task_track_started)  # Deve ser True
```

### Solução 2: Remover Chord e Usar Task Única (RECOMENDADO)

**Problema do Chord:**
- Complexo (header + body)
- Depende de backend de resultados
- Pode travar silenciosamente

**Alternativa:**
- Criar **1 task batch** que processa todas as turmas sequencialmente
- Não depende de chord
- Mais simples e confiável

**Exemplo:**
```python
# Ao invés de:
chord(group(task1, task2, task3))(callback)

# Usar:
batch_task.delay(class_ids=[id1, id2, id3])
```

### Solução 3: Adicionar Timeout e Retry no Chord (PALIATIVO)

```python
chord_sig = chord(header)(
    build_zip_and_upload_answer_sheets.s(...).set(
        countdown=10,  # Esperar 10s após header terminar
        retry=True,
        retry_policy={
            'max_retries': 3,
            'interval_start': 5,
            'interval_step': 5,
        }
    )
)
```

---

## 🔧 Correção Recomendada

### Opção A: Remover Chord (MAIS SIMPLES)

**Vantagens:**
- ✅ Não depende de backend de resultados
- ✅ Mais simples de debugar
- ✅ Menos pontos de falha

**Desvantagens:**
- ❌ Processa turmas sequencialmente (mais lento)
- ❌ Não aproveita paralelismo do Celery

### Opção B: Corrigir Configuração do Chord (MAIS COMPLEXO)

**Vantagens:**
- ✅ Mantém paralelismo (mais rápido)
- ✅ Aproveita workers disponíveis

**Desvantagens:**
- ❌ Mais complexo de debugar
- ❌ Depende de backend de resultados funcionando

---

## 📝 Próximos Passos

### 1. Verificar Configuração do Celery:

```bash
# No terminal do Celery
python -c "from app.report_analysis.celery_app import celery_app; print(celery_app.conf.result_backend)"
```

### 2. Verificar Logs do Redis:

```bash
# Ver se há erros de conexão
redis-cli ping
```

### 3. Testar Chord Manualmente:

```python
from celery import chord, group
from app.services.celery_tasks.answer_sheet_tasks import (
    generate_answer_sheets_single_class_async,
    build_zip_and_upload_answer_sheets
)

# Testar chord simples
header = group([
    generate_answer_sheets_single_class_async.s(class_id="test-id", ...)
])
callback = build_zip_and_upload_answer_sheets.s(...)
result = chord(header)(callback).apply_async()
print(result.id)
```

---

## 🎯 Resumo

| Aspecto | Status |
|---------|--------|
| **Tasks individuais** | ✅ Executam com sucesso |
| **Callback do chord** | ❌ Nunca é chamado |
| **Job status** | ❌ Fica em "processing" |
| **PDFs gerados** | ✅ Criados mas ❌ inacessíveis |
| **Celery** | ❌ Fica ocioso após tasks |

**Causa provável:** Configuração incorreta do `result_backend` ou problema com chord do Celery.

**Solução recomendada:** Remover chord e usar task batch única (mais simples e confiável).

---

**Status:** 🔴 PROBLEMA IDENTIFICADO - Aguardando decisão sobre correção
