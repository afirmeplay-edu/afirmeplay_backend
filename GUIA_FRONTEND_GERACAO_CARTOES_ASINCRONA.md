# 🚀 Guia Frontend: Geração Assíncrona de Cartões de Resposta

## 📋 Visão Geral

A geração de cartões de resposta agora é **ASSÍNCRONA** via Celery para evitar timeouts do Gunicorn.

**Por quê?**
- Cada PDF leva ~40 segundos para gerar
- Turma com 20 alunos = 20 PDFs = ~800 segundos (13 minutos)
- Gunicorn timeout = 30 segundos
- **Solução:** Processar em background via Celery

---

## 🔄 Mudanças na API

### **ANTES (Síncrono - REMOVIDO):**

```javascript
POST /answer-sheets/generate
// Retornava ZIP diretamente após longa espera
// ❌ Timeout com turmas grandes
```

### **AGORA (Assíncrono - NOVO):**

```javascript
// 1. Iniciar geração (retorna imediatamente)
POST /answer-sheets/generate
→ 202 Accepted + task_id

// 2. Verificar status (polling)
GET /answer-sheets/task/{task_id}/status
→ Status da geração

// 3. Download (quando concluído)
// ⚠️ PDFs ficam disponíveis via query individual
```

---

## 🎯 Fluxo Completo

```
Frontend                    Backend                     Celery Worker
   |                           |                              |
   |--[POST /generate]-------->|                              |
   |                           |--[task.delay()]------------->|
   |<--[202 + task_id]---------|                              |
   |                           |                              |
   |                           |                        [Gerando PDFs]
   |                           |                              |
   |--[GET /task/status]------>|                              |
   |<--[processing]------------|                              |
   |                           |                              |
   |   (aguarda 2s)            |                              |
   |                           |                              |
   |--[GET /task/status]------>|                              |
   |<--[processing]------------|                              |
   |                           |                              |
   |   (aguarda 2s)            |                              |
   |                           |                              |
   |--[GET /task/status]------>|<--[SUCCESS]------------------|
   |<--[completed + result]----|                              |
   |                           |                              |
```

---

## 📡 **API ENDPOINTS**

### **1. POST `/answer-sheets/generate`**

Inicia a geração assíncrona de cartões de resposta.

**Request:**
```json
{
  "class_id": "uuid-da-turma",
  "num_questions": 22,
  "correct_answers": {
    "1": "C",
    "2": "A",
    ...
  },
  "test_data": {
    "title": "Prova de Matemática",
    "municipality": "São Paulo",
    "state": "SP",
    ...
  },
  "use_blocks": true,
  "blocks_config": {
    "num_blocks": 2,
    "questions_per_block": 11
  },
  "questions_options": {  // Opcional
    "1": ["A", "B", "C"],
    "2": ["A", "B", "C", "D"],
    ...
  }
}
```

**Response: `202 Accepted`**
```json
{
  "status": "processing",
  "message": "Cartões de resposta sendo gerados em background...",
  "task_id": "abc123-def456-...",
  "gabarito_id": "uuid-do-gabarito",
  "class_id": "uuid-da-turma",
  "class_name": "5º Ano A",
  "num_questions": 22,
  "polling_url": "/answer-sheets/task/abc123.../status"
}
```

---

### **2. GET `/answer-sheets/task/{task_id}/status`**

Consulta o status da geração.

**Response: `200 OK`**

**Status: `pending`**
```json
{
  "status": "pending",
  "message": "Task aguardando processamento",
  "task_id": "abc123..."
}
```

**Status: `processing`**
```json
{
  "status": "processing",
  "message": "Cartões sendo gerados...",
  "task_id": "abc123..."
}
```

**Status: `completed`**
```json
{
  "status": "completed",
  "message": "Cartões gerados com sucesso",
  "task_id": "abc123...",
  "result": {
    "success": true,
    "class_id": "uuid...",
    "class_name": "5º Ano A",
    "num_questions": 22,
    "total_students": 20,
    "generated_sheets": 20,
    "gabarito_id": "uuid...",
    "sheets": [
      {
        "student_id": "uuid...",
        "student_name": "João Silva",
        "has_pdf": true
      },
      ...
    ]
  }
}
```

**Status: `failed`**
```json
{
  "status": "failed",
  "message": "Erro ao gerar cartões",
  "task_id": "abc123...",
  "error": "Mensagem de erro"
}
```

---

## 💻 **EXEMPLOS DE IMPLEMENTAÇÃO**

### **React/TypeScript**

```typescript
interface GenerateResponse {
  status: string;
  task_id: string;
  gabarito_id: string;
  class_name: string;
  polling_url: string;
}

interface TaskStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  result?: {
    success: boolean;
    generated_sheets: number;
    total_students: number;
    sheets: Array<{
      student_id: string;
      student_name: string;
      has_pdf: boolean;
    }>;
  };
  error?: string;
}

async function generateAnswerSheets(data: any) {
  // 1. Iniciar geração
  const response = await fetch('/answer-sheets/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(data)
  });

  if (response.status !== 202) {
    throw new Error('Erro ao iniciar geração');
  }

  const initData: GenerateResponse = await response.json();
  
  // 2. Polling do status
  return pollTaskStatus(initData.task_id);
}

async function pollTaskStatus(taskId: string): Promise<TaskStatus> {
  const maxAttempts = 60; // 60 tentativas = 2 minutos
  const interval = 2000; // 2 segundos

  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/answer-sheets/task/${taskId}/status`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    const status: TaskStatus = await response.json();

    if (status.status === 'completed') {
      return status;
    }

    if (status.status === 'failed') {
      throw new Error(status.error || 'Geração falhou');
    }

    // Aguardar antes de tentar novamente
    await new Promise(resolve => setTimeout(resolve, interval));
  }

  throw new Error('Timeout: geração demorou muito');
}

// Uso com UI
async function handleGenerate() {
  try {
    setLoading(true);
    setMessage('Iniciando geração...');

    const result = await generateAnswerSheets(formData);

    setMessage(`✅ ${result.result.generated_sheets} cartões gerados!`);
    setLoading(false);

    // Mostrar lista de cartões gerados
    setSheets(result.result.sheets);

  } catch (error) {
    setMessage(`❌ Erro: ${error.message}`);
    setLoading(false);
  }
}
```

---

### **Vue.js 3 (Composition API)**

```vue
<template>
  <div>
    <button @click="generateSheets" :disabled="loading">
      {{ loading ? 'Gerando...' : 'Gerar Cartões' }}
    </button>

    <div v-if="loading" class="progress">
      <p>{{ message }}</p>
      <progress-spinner />
    </div>

    <div v-if="result && result.status === 'completed'" class="success">
      <h3>✅ Geração concluída!</h3>
      <p>{{ result.result.generated_sheets }} de {{ result.result.total_students }} cartões gerados</p>
      
      <ul>
        <li v-for="sheet in result.result.sheets" :key="sheet.student_id">
          {{ sheet.student_name }} - 
          <span v-if="sheet.has_pdf">✅ PDF gerado</span>
          <span v-else>❌ Erro</span>
        </li>
      </ul>
    </div>

    <div v-if="error" class="error">
      ❌ {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

const auth = useAuthStore();
const loading = ref(false);
const message = ref('');
const result = ref(null);
const error = ref(null);

async function generateSheets() {
  loading.value = true;
  error.value = null;
  message.value = 'Iniciando geração...';

  try {
    // 1. Iniciar geração
    const response = await fetch('/answer-sheets/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${auth.token}`
      },
      body: JSON.stringify({
        class_id: 'uuid...',
        num_questions: 22,
        // ... outros dados
      })
    });

    const data = await response.json();

    if (response.status !== 202) {
      throw new Error(data.error || 'Erro ao iniciar');
    }

    // 2. Polling
    message.value = 'Gerando cartões...';
    result.value = await pollStatus(data.task_id);

  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function pollStatus(taskId) {
  const maxAttempts = 60;
  const interval = 2000;

  for (let i = 0; i < maxAttempts; i++) {
    const response = await fetch(`/answer-sheets/task/${taskId}/status`, {
      headers: { 'Authorization': `Bearer ${auth.token}` }
    });

    const status = await response.json();

    if (status.status === 'completed') {
      return status;
    }

    if (status.status === 'failed') {
      throw new Error(status.error);
    }

    message.value = `Gerando... (${i + 1}/${maxAttempts})`;
    await new Promise(resolve => setTimeout(resolve, interval));
  }

  throw new Error('Timeout');
}
</script>
```

---

## ⚠️ **IMPORTANTE**

### **1. PDFs não retornam mais via ZIP**

Os PDFs são gerados mas **NÃO são retornados diretamente**. Para baixar os PDFs:

**OPÇÃO A:** Regenerar a partir do gabarito
```
GET /answer-sheets/gabarito/{gabarito_id}/regenerate
```

**OPÇÃO B:** Buscar cada PDF individualmente (se implementado)
```
GET /answer-sheets/pdf/{student_id}/{gabarito_id}
```

### **2. Timeout do Polling**

- **Timeout recomendado:** 2 minutos (60 tentativas × 2 segundos)
- **Turma pequena (10 alunos):** ~6-8 minutos
- **Turma grande (30 alunos):** ~15-20 minutos

Ajuste conforme necessário!

### **3. Feedback ao Usuário**

```
✅ BOM:
"Gerando cartões... (10/20 tentativas)"
"Aguarde, isso pode levar alguns minutos..."

❌ RUIM:
"Processando..." (sem indicação de progresso)
"Carregando..." (usuário não sabe quanto tempo vai demorar)
```

---

## 🔧 **TROUBLESHOOTING**

### **Problema:** Task fica em `pending` eternamente

**Causa:** Celery worker não está rodando  
**Solução:**
```bash
# Verificar worker
celery -A app.report_analysis.celery_app status

# Iniciar worker
celery -A app.report_analysis.celery_app worker --loglevel=info
```

### **Problema:** Task falha com erro de memória

**Causa:** Turma muito grande (50+ alunos)  
**Solução:**
- Dividir em lotes menores
- Aumentar memória do worker Celery

### **Problema:** PDFs gerados mas não aparecem

**Causa:** Os PDFs são gerados em memória, não salvos em disco  
**Solução:** Implementar endpoint de regeneração ou salvar PDFs temporariamente

---

## 📚 **MAIS INFORMAÇÕES**

Ver também:
- `GUIA_FRONTEND_GERACAO_ASINCRONA.md` - Provas físicas assíncronas
- `app/services/celery_tasks/README.md` - Documentação técnica do Celery
- `app/routes/answer_sheet_routes.py` - Código fonte das rotas

---

**Dúvidas?** Consulte os logs do Celery worker ou entre em contato com a equipe de backend.
