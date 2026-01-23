# 🔄 GUIA FRONTEND: Geração Assíncrona de Formulários Físicos

## 🎯 **PROBLEMA:**

A geração de formulários físicos agora é **ASSÍNCRONA** com Celery. Isso significa que:

1. ✅ A API retorna **imediatamente** (não espera os PDFs serem gerados)
2. ✅ Os PDFs são gerados **em background** pelo Celery
3. ❌ O frontend precisa fazer **POLLING** para verificar quando terminou

---

## 📊 **FLUXO COMPLETO:**

```
1. Frontend faz POST para gerar formulários
   ↓
2. Backend retorna 202 Accepted + task_id (imediatamente)
   ↓
3. Celery processa em background (pode levar minutos)
   ↓
4. Frontend faz polling em /task/{task_id}/status
   ↓
5. Quando status = "completed", exibe resultados
```

---

## 🔌 **API ENDPOINTS:**

### **1️⃣ DISPARAR GERAÇÃO (assíncrono):**

```http
POST /physical-tests/test/<test_id>/generate-forms
Authorization: Bearer <token>
Content-Type: application/json

{
  "force_regenerate": false  // Opcional
}
```

**Resposta (202 Accepted):**
```json
{
  "status": "processing",
  "message": "Formulários sendo gerados em background. Use o task_id para verificar o status.",
  "task_id": "abc-123-def-456",
  "test_id": "test-uuid-789",
  "test_title": "AVALIE TEOTONIO 2026",
  "polling_url": "/physical-tests/task/abc-123-def-456/status"
}
```

**⚠️ IMPORTANTE:** Esta resposta é **IMEDIATA**! Os formulários **NÃO foram gerados ainda**!

---

### **2️⃣ VERIFICAR STATUS (polling):**

```http
GET /physical-tests/task/<task_id>/status
Authorization: Bearer <token>
```

**Possíveis Respostas:**

#### **A. Processando:**
```json
{
  "status": "processing",
  "message": "Gerando formulários PDF (isso pode levar alguns minutos)...",
  "task_id": "abc-123-def-456"
}
```

#### **B. Concluído (SUCESSO):**
```json
{
  "status": "completed",
  "message": "Formulários gerados com sucesso para 35 alunos",
  "task_id": "abc-123-def-456",
  "result": {
    "success": true,
    "test_id": "test-uuid-789",
    "test_title": "AVALIE TEOTONIO 2026",
    "total_questions": 22,
    "total_students": 35,
    "generated_forms": 35,
    "gabarito_id": "gabarito-uuid-abc",
    "forms": [
      {
        "student_id": "student-uuid-1",
        "student_name": "João Silva",
        "form_id": "form-uuid-1",
        "form_type": "institutional",
        "created_at": "2026-01-22T22:11:30.000000"
      }
      // ... mais formulários
    ]
  }
}
```

#### **C. Erro:**
```json
{
  "status": "failed",
  "message": "Erro ao gerar formulários",
  "task_id": "abc-123-def-456",
  "error": "Descrição do erro"
}
```

#### **D. Tentando novamente (após erro):**
```json
{
  "status": "retrying",
  "message": "Erro detectado. Tentando novamente (tentativa 1/2)...",
  "task_id": "abc-123-def-456",
  "retry_count": 1
}
```

---

## 💻 **IMPLEMENTAÇÃO NO FRONTEND:**

### **REACT - Completo com UI:**

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function GeneratePhysicalForms({ testId }) {
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);

  const generateForms = async () => {
    try {
      setLoading(true);
      setError(null);
      setProgress(10);
      
      const token = localStorage.getItem('token');
      
      // 1. DISPARAR GERAÇÃO (retorna imediatamente)
      const response = await axios.post(
        `/physical-tests/test/${testId}/generate-forms`,
        { force_regenerate: false },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (response.status === 202) {
        const data = response.data;
        setTaskId(data.task_id);
        setStatus('processing');
        setProgress(20);
        
        // 2. INICIAR POLLING
        startPolling(data.task_id, token);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Erro ao iniciar geração');
      setLoading(false);
    }
  };

  const startPolling = (taskId, token) => {
    // Fazer polling a cada 3 segundos
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(
          `/physical-tests/task/${taskId}/status`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        
        const data = response.data;
        setStatus(data.status);
        
        // Atualizar progresso visual
        if (data.status === 'processing') {
          setProgress(prev => Math.min(prev + 5, 80));
        }
        
        // SUCESSO: parar polling e exibir resultado
        if (data.status === 'completed') {
          clearInterval(interval);
          setProgress(100);
          setResult(data.result);
          setLoading(false);
          
          // Opcional: mostrar notificação de sucesso
          alert(`✅ ${data.result.generated_forms} formulários gerados com sucesso!`);
        }
        
        // ERRO: parar polling e exibir erro
        if (data.status === 'failed') {
          clearInterval(interval);
          setError(data.error || 'Erro ao gerar formulários');
          setLoading(false);
        }
        
      } catch (err) {
        clearInterval(interval);
        setError('Erro ao verificar status da geração');
        setLoading(false);
      }
    }, 3000); // Polling a cada 3 segundos
    
    // Timeout de segurança (15 minutos)
    setTimeout(() => {
      clearInterval(interval);
      if (loading) {
        setError('Timeout: A geração está demorando mais do que o esperado');
        setLoading(false);
      }
    }, 15 * 60 * 1000);
  };

  return (
    <div className="generate-forms-container">
      <h2>Gerar Formulários Físicos</h2>
      
      {/* Botão de Gerar */}
      {!loading && !result && (
        <button onClick={generateForms} className="btn-primary">
          📄 Gerar Formulários
        </button>
      )}
      
      {/* Indicador de Progresso */}
      {loading && (
        <div className="loading-section">
          <div className="progress-bar-container">
            <div 
              className="progress-bar" 
              style={{ width: `${progress}%` }}
            >
              {progress}%
            </div>
          </div>
          
          <p className="status-message">
            {status === 'processing' && '⏳ Gerando formulários PDF...'}
            {status === 'retrying' && '🔄 Tentando novamente...'}
          </p>
          
          <p className="info-text">
            <small>Isso pode levar alguns minutos. Não feche esta página.</small>
          </p>
        </div>
      )}
      
      {/* Erro */}
      {error && (
        <div className="error-box">
          <p>❌ Erro: {error}</p>
          <button onClick={generateForms}>
            🔄 Tentar Novamente
          </button>
        </div>
      )}
      
      {/* Resultado (Sucesso) */}
      {result && (
        <div className="success-box">
          <h3>✅ Formulários Gerados com Sucesso!</h3>
          
          <div className="summary">
            <p><strong>Prova:</strong> {result.test_title}</p>
            <p><strong>Questões:</strong> {result.total_questions}</p>
            <p><strong>Alunos:</strong> {result.total_students}</p>
            <p><strong>Formulários:</strong> {result.generated_forms}</p>
          </div>
          
          {/* Lista de Formulários */}
          <div className="forms-list">
            <h4>Formulários Gerados:</h4>
            <table>
              <thead>
                <tr>
                  <th>Aluno</th>
                  <th>Data</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {result.forms.map(form => (
                  <tr key={form.form_id}>
                    <td>{form.student_name}</td>
                    <td>{new Date(form.created_at).toLocaleString('pt-BR')}</td>
                    <td>
                      <button onClick={() => downloadForm(form.form_id)}>
                        📥 Baixar PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          <button 
            onClick={() => window.location.reload()} 
            className="btn-secondary"
          >
            🔄 Gerar Novamente
          </button>
        </div>
      )}
    </div>
  );
}

export default GeneratePhysicalForms;
```

---

### **VUE.JS - Versão Simplificada:**

```vue
<template>
  <div class="generate-forms">
    <h2>Gerar Formulários Físicos</h2>
    
    <!-- Botão -->
    <button 
      v-if="!loading && !result"
      @click="generateForms"
      class="btn-primary"
    >
      📄 Gerar Formulários
    </button>
    
    <!-- Loading -->
    <div v-if="loading" class="loading">
      <div class="progress-bar">
        <div :style="{ width: progress + '%' }">{{ progress }}%</div>
      </div>
      <p>{{ statusMessage }}</p>
    </div>
    
    <!-- Erro -->
    <div v-if="error" class="error">
      <p>❌ {{ error }}</p>
      <button @click="generateForms">Tentar Novamente</button>
    </div>
    
    <!-- Resultado -->
    <div v-if="result" class="success">
      <h3>✅ Sucesso!</h3>
      <p>{{ result.generated_forms }} formulários gerados</p>
      <!-- ... lista de formulários ... -->
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  props: ['testId'],
  data() {
    return {
      loading: false,
      taskId: null,
      progress: 0,
      result: null,
      error: null,
      statusMessage: '',
      pollingInterval: null
    };
  },
  methods: {
    async generateForms() {
      try {
        this.loading = true;
        this.error = null;
        this.progress = 10;
        
        const token = localStorage.getItem('token');
        
        // Disparar geração
        const response = await axios.post(
          `/physical-tests/test/${this.testId}/generate-forms`,
          { force_regenerate: false },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        
        if (response.status === 202) {
          this.taskId = response.data.task_id;
          this.progress = 20;
          this.startPolling(token);
        }
      } catch (err) {
        this.error = err.response?.data?.error || 'Erro ao gerar';
        this.loading = false;
      }
    },
    
    startPolling(token) {
      this.pollingInterval = setInterval(async () => {
        try {
          const response = await axios.get(
            `/physical-tests/task/${this.taskId}/status`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          
          const data = response.data;
          this.statusMessage = data.message;
          
          if (data.status === 'processing') {
            this.progress = Math.min(this.progress + 5, 80);
          }
          
          if (data.status === 'completed') {
            clearInterval(this.pollingInterval);
            this.progress = 100;
            this.result = data.result;
            this.loading = false;
          }
          
          if (data.status === 'failed') {
            clearInterval(this.pollingInterval);
            this.error = data.error;
            this.loading = false;
          }
        } catch (err) {
          clearInterval(this.pollingInterval);
          this.error = 'Erro ao verificar status';
          this.loading = false;
        }
      }, 3000);
    }
  },
  beforeUnmount() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }
  }
};
</script>
```

---

### **JAVASCRIPT VANILLA - Mínimo:**

```javascript
async function generatePhysicalForms(testId) {
  const token = localStorage.getItem('token');
  
  try {
    // 1. Disparar geração
    const response = await fetch(
      `/physical-tests/test/${testId}/generate-forms`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ force_regenerate: false })
      }
    );
    
    if (response.status === 202) {
      const data = await response.json();
      console.log('✅ Geração iniciada, task_id:', data.task_id);
      
      // 2. Iniciar polling
      pollTaskStatus(data.task_id, token);
    }
  } catch (error) {
    console.error('❌ Erro:', error);
  }
}

async function pollTaskStatus(taskId, token) {
  const interval = setInterval(async () => {
    try {
      const response = await fetch(
        `/physical-tests/task/${taskId}/status`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      
      const data = await response.json();
      console.log('Status:', data.status);
      
      if (data.status === 'completed') {
        clearInterval(interval);
        console.log('✅ Concluído!', data.result);
        
        // Exibir resultado
        displayResult(data.result);
      }
      
      if (data.status === 'failed') {
        clearInterval(interval);
        console.error('❌ Erro:', data.error);
        alert('Erro ao gerar formulários: ' + data.error);
      }
    } catch (error) {
      clearInterval(interval);
      console.error('❌ Erro no polling:', error);
    }
  }, 3000); // Polling a cada 3 segundos
}

function displayResult(result) {
  alert(`✅ ${result.generated_forms} formulários gerados com sucesso!`);
  // Atualizar UI com os formulários
}
```

---

## 📋 **CHECKLIST PARA O FRONTEND:**

- [ ] Entender que a geração é **assíncrona** (não é imediata)
- [ ] Receber o `task_id` da resposta `202 Accepted`
- [ ] Implementar **polling** em `/task/{task_id}/status`
- [ ] Fazer polling **a cada 2-3 segundos**
- [ ] Verificar `status` em cada poll:
  - `processing` → continuar polling
  - `completed` → parar e exibir resultado
  - `failed` → parar e exibir erro
- [ ] Implementar **timeout** de segurança (15 minutos)
- [ ] Exibir **indicador de progresso** visual
- [ ] Limpar **intervalo** quando componente desmontar
- [ ] Avisar usuário para **não fechar a página**

---

## ⏱️ **TEMPO ESTIMADO:**

A geração pode levar de **10 segundos a 10 minutos**, dependendo de:
- Número de alunos (1 aluno = ~3-5 segundos)
- Número de questões na prova
- Carga do servidor

**Exemplo:**
- 1 aluno: ~5 segundos
- 10 alunos: ~30 segundos
- 35 alunos: ~2 minutos
- 100 alunos: ~5-7 minutos

---

## 🎯 **EXEMPLO VISUAL NO FRONTEND:**

```
┌──────────────────────────────────────────┐
│ Gerar Formulários Físicos                │
├──────────────────────────────────────────┤
│                                          │
│ [📄 Gerar Formulários]  ← Botão inicial │
│                                          │
└──────────────────────────────────────────┘

       ↓ (Após clicar)

┌──────────────────────────────────────────┐
│ Gerando Formulários...                   │
├──────────────────────────────────────────┤
│                                          │
│ ⏳ Gerando formulários PDF...            │
│ ████████████░░░░░░░░░░░░ 60%            │
│                                          │
│ Isso pode levar alguns minutos.          │
│ Não feche esta página.                   │
│                                          │
└──────────────────────────────────────────┘

       ↓ (Após concluir)

┌──────────────────────────────────────────┐
│ ✅ Formulários Gerados com Sucesso!      │
├──────────────────────────────────────────┤
│                                          │
│ Prova: AVALIE TEOTONIO 2026              │
│ Questões: 22                             │
│ Alunos: 35                               │
│ Formulários: 35                          │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ Aluno          │ Data     │ Baixar │  │
│ ├────────────────┼──────────┼────────┤  │
│ │ João Silva     │ 22/01    │ [PDF]  │  │
│ │ Maria Santos   │ 22/01    │ [PDF]  │  │
│ │ ...            │ ...      │ ...    │  │
│ └────────────────────────────────────┘  │
│                                          │
│ [🔄 Gerar Novamente]                     │
└──────────────────────────────────────────┘
```

---

## ✅ **RESUMO:**

1. **POST** `/generate-forms` → Retorna `202` + `task_id` (imediato)
2. **POLLING** em `/task/{task_id}/status` a cada 3 segundos
3. **QUANDO** `status === 'completed'` → Exibir resultado
4. **PARAR** polling quando concluir ou falhar

**O frontend PRECISA implementar o polling, senão nunca verá os formulários gerados!** 🚀
