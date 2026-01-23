# 📘 Exemplo de Uso no Frontend - Geração Assíncrona de Formulários

Este documento mostra como o frontend deve consumir a API de geração assíncrona de formulários físicos usando Celery.

---

## 🎯 **Fluxo Completo**

```
1. Frontend dispara geração (POST)
   ↓
2. Backend retorna task_id imediatamente (202 Accepted)
   ↓
3. Frontend faz polling a cada 3 segundos (GET /task/{task_id}/status)
   ↓
4. Backend retorna status: "pending" → "processing" → "completed"
   ↓
5. Quando completed, frontend exibe formulários gerados
```

---

## 📝 **Exemplo Completo em JavaScript**

### **1. Disparar Geração (POST)**

```javascript
// Função para iniciar geração de formulários
async function generatePhysicalForms(testId) {
  try {
    const response = await fetch(`/physical-tests/test/${testId}/generate-forms`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,  // Seu token JWT
      },
      body: JSON.stringify({
        force_regenerate: false  // Opcional
      })
    });

    if (response.status === 202) {
      // Sucesso! Geração iniciada
      const data = await response.json();
      
      console.log('✅ Geração iniciada:', data);
      // {
      //   "status": "processing",
      //   "message": "Formulários sendo gerados em background...",
      //   "task_id": "abc-123-def-456",
      //   "test_id": "test-uuid",
      //   "test_title": "Avaliação de Matemática",
      //   "polling_url": "/physical-tests/task/abc-123-def-456/status"
      // }
      
      // Iniciar polling para acompanhar progresso
      return await pollTaskStatus(data.task_id);
      
    } else if (response.status === 404) {
      throw new Error('Prova não encontrada');
    } else if (response.status === 403) {
      throw new Error('Você não tem permissão para gerar formulários desta prova');
    } else {
      const error = await response.json();
      throw new Error(error.error || 'Erro ao iniciar geração');
    }
    
  } catch (error) {
    console.error('❌ Erro:', error);
    throw error;
  }
}
```

---

### **2. Polling - Verificar Status (GET)**

```javascript
// Função para fazer polling e acompanhar progresso
async function pollTaskStatus(taskId, onProgress = null) {
  const maxAttempts = 200;  // 200 tentativas × 3s = 10 minutos
  let attempts = 0;
  
  return new Promise((resolve, reject) => {
    const interval = setInterval(async () => {
      attempts++;
      
      try {
        const response = await fetch(`/physical-tests/task/${taskId}/status`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
          }
        });
        
        if (!response.ok) {
          clearInterval(interval);
          reject(new Error('Erro ao verificar status'));
          return;
        }
        
        const data = await response.json();
        console.log(`📊 Status (tentativa ${attempts}):`, data.status);
        
        // Callback para atualizar UI (loading, progress bar, etc)
        if (onProgress) {
          onProgress(data);
        }
        
        // Verificar estados finais
        if (data.status === 'completed') {
          clearInterval(interval);
          console.log('✅ Geração concluída!', data.result);
          resolve(data.result);
          
        } else if (data.status === 'failed') {
          clearInterval(interval);
          console.error('❌ Geração falhou:', data.error);
          reject(new Error(data.error || 'Erro na geração'));
          
        } else if (attempts >= maxAttempts) {
          clearInterval(interval);
          reject(new Error('Timeout: geração demorou muito'));
          
        } else {
          // Estados intermediários: pending, processing, retrying
          console.log(`⏳ ${data.message}`);
        }
        
      } catch (error) {
        clearInterval(interval);
        reject(error);
      }
      
    }, 3000);  // Polling a cada 3 segundos
  });
}
```

---

### **3. Exemplo Completo com UI (React/Vue)**

```javascript
// Componente React
import React, { useState } from 'react';

function GenerateFormsButton({ testId }) {
  const [status, setStatus] = useState('idle');  // idle, loading, success, error
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    setStatus('loading');
    setError(null);
    setProgress({ message: 'Iniciando geração...' });

    try {
      // 1. Disparar geração
      const response = await fetch(`/physical-tests/test/${testId}/generate-forms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`,
        },
        body: JSON.stringify({ force_regenerate: false })
      });

      if (response.status !== 202) {
        throw new Error('Erro ao iniciar geração');
      }

      const data = await response.json();
      const taskId = data.task_id;

      // 2. Polling
      const pollResult = await pollTaskStatus(
        taskId,
        (progressData) => {
          // Atualizar UI a cada polling
          setProgress({
            status: progressData.status,
            message: progressData.message
          });
        }
      );

      // 3. Sucesso!
      setStatus('success');
      setResult(pollResult);
      
      console.log('✅ Formulários gerados:', pollResult);
      // {
      //   "success": true,
      //   "test_id": "...",
      //   "test_title": "Avaliação...",
      //   "generated_forms": 35,
      //   "total_students": 35,
      //   "forms": [...]
      // }

    } catch (err) {
      setStatus('error');
      setError(err.message);
      console.error('❌ Erro:', err);
    }
  };

  return (
    <div>
      <button 
        onClick={handleGenerate} 
        disabled={status === 'loading'}
      >
        {status === 'loading' ? 'Gerando...' : 'Gerar Formulários'}
      </button>

      {status === 'loading' && progress && (
        <div className="progress">
          <div className="spinner"></div>
          <p>{progress.message}</p>
          <p><small>Status: {progress.status}</small></p>
        </div>
      )}

      {status === 'success' && result && (
        <div className="success">
          ✅ {result.message}
          <p>Formulários gerados: {result.generated_forms}/{result.total_students}</p>
          <ul>
            {result.forms.map(form => (
              <li key={form.form_id}>
                {form.student_name} - {form.form_id}
              </li>
            ))}
          </ul>
        </div>
      )}

      {status === 'error' && (
        <div className="error">
          ❌ Erro: {error}
        </div>
      )}
    </div>
  );
}

// Funções auxiliares (mesmas do exemplo anterior)
async function pollTaskStatus(taskId, onProgress) {
  // ... (código do exemplo 2)
}

function getAuthToken() {
  return localStorage.getItem('authToken');
}
```

---

## 🎨 **Estados da Task**

| Status | Descrição | Ação do Frontend |
|--------|-----------|------------------|
| `pending` | Aguardando processamento | Mostrar loading |
| `processing` | Gerando PDFs | Mostrar loading + progresso |
| `retrying` | Tentando novamente após erro | Mostrar "Tentando novamente..." |
| `completed` | Concluído com sucesso ✅ | Mostrar resultado |
| `failed` | Falhou após retries ❌ | Mostrar erro |

---

## 📊 **Exemplo de Timeline**

```
00:00 - Frontend: POST /generate-forms
00:00 - Backend: Retorna task_id (202 Accepted)
00:00 - Frontend: Inicia polling

00:03 - Frontend: GET /task/{id}/status → "pending"
00:06 - Frontend: GET /task/{id}/status → "processing"
00:09 - Frontend: GET /task/{id}/status → "processing"
00:12 - Frontend: GET /task/{id}/status → "processing"
...
02:30 - Frontend: GET /task/{id}/status → "completed" ✅
02:30 - Frontend: Para polling e exibe resultado
```

---

## 🚨 **Tratamento de Erros**

```javascript
async function generateWithErrorHandling(testId) {
  try {
    const result = await generatePhysicalForms(testId);
    
    // Sucesso
    showSuccessMessage(`${result.generated_forms} formulários gerados!`);
    refreshFormsList();
    
  } catch (error) {
    // Erro
    if (error.message.includes('não encontrada')) {
      showErrorMessage('Prova não encontrada');
    } else if (error.message.includes('permissão')) {
      showErrorMessage('Você não tem permissão para gerar formulários');
    } else if (error.message.includes('Timeout')) {
      showErrorMessage('A geração demorou muito. Tente novamente mais tarde.');
    } else {
      showErrorMessage(`Erro: ${error.message}`);
    }
  }
}
```

---

## ⚡ **Dicas de Performance**

1. **Polling Interval:** 
   - Use 3 segundos para melhor balanço entre responsividade e carga no servidor
   - Para operações muito longas, pode aumentar para 5 segundos

2. **Timeout:**
   - Configure timeout máximo (ex: 10 minutos)
   - Se ultrapassar, mostre mensagem e permita tentar novamente

3. **Cache:**
   - Se resultado já foi obtido, pode cachear temporariamente
   - Evite disparar múltiplas gerações simultaneamente

4. **Feedback Visual:**
   - Mostre spinner/loading durante polling
   - Exiba mensagens descritivas ("Gerando PDF 15/35...")
   - Progress bar se possível

---

## 📱 **Exemplo Axios (alternativa)**

```javascript
import axios from 'axios';

async function generateForms(testId) {
  // 1. Disparar geração
  const { data } = await axios.post(
    `/physical-tests/test/${testId}/generate-forms`,
    { force_regenerate: false },
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  );

  // 2. Polling
  while (true) {
    await new Promise(resolve => setTimeout(resolve, 3000));  // Aguardar 3s
    
    const { data: status } = await axios.get(
      `/physical-tests/task/${data.task_id}/status`,
      { headers: { Authorization: `Bearer ${token}` } }
    );

    if (status.status === 'completed') {
      return status.result;
    } else if (status.status === 'failed') {
      throw new Error(status.error);
    }
    
    console.log('⏳', status.message);
  }
}
```

---

## ✅ **Checklist de Implementação**

- [ ] Implementar botão de "Gerar Formulários"
- [ ] Adicionar loading/spinner durante geração
- [ ] Implementar polling com intervalo de 3 segundos
- [ ] Mostrar mensagens de progresso
- [ ] Tratar estados: pending, processing, completed, failed
- [ ] Implementar timeout (10 minutos)
- [ ] Mostrar resultado com lista de formulários gerados
- [ ] Tratamento de erros (404, 403, 500, timeout)
- [ ] Desabilitar botão durante geração
- [ ] Permitir cancelamento (opcional)

---

**🎉 Pronto! Seu frontend está preparado para consumir a API assíncrona com Celery!**
