# 🎨 GUIA FRONTEND: Status de Correção de Formulários Físicos

## 🚀 **IMPLEMENTADO:**

A funcionalidade de rastreamento de correção de formulários físicos está **ATIVA** no backend!

### **O que foi implementado:**
- ✅ Método `_marcar_formulario_como_corrigido` no pipeline OMR
- ✅ Atualização automática de `PhysicalTestForm` após correção
- ✅ API já retorna todos os campos necessários

---

## 📡 **API DISPONÍVEL:**

### **Endpoint:** `GET /physical-tests/test/<test_id>/forms`

**Headers:**
```javascript
{
  "Authorization": "Bearer <token>"
}
```

**Resposta:**
```json
{
  "forms": [
    {
      "id": "form-uuid-123",
      "student_id": "student-uuid-456",
      "student_name": "João da Silva",
      "test_id": "test-uuid-789",
      "class_test_id": "class-test-uuid",
      
      // ✅ Campos de status de correção
      "status": "corrigido",              // "gerado" | "corrigido" | "processado"
      "is_corrected": true,               // Boolean
      "corrected_at": "2026-01-22T20:45:30.123456",  // ISO 8601
      
      // Outros campos úteis
      "generated_at": "2026-01-22T10:00:00.000000",
      "answer_sheet_sent_at": "2026-01-22T20:45:30.123456",
      "qr_code_data": "...",
      "has_pdf_data": true,
      "has_answer_sheet_data": false,
      "has_correction_data": false
    },
    {
      "id": "form-uuid-124",
      "student_name": "Maria Santos",
      "status": "gerado",                 // Ainda não corrigido
      "is_corrected": false,
      "corrected_at": null,
      // ...
    }
  ],
  "total": 2
}
```

---

## 💻 **EXEMPLOS DE IMPLEMENTAÇÃO:**

### **1️⃣ REACT - Listar Formulários com Status**

```jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

function PhysicalTestForms({ testId }) {
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, corrected: 0, pending: 0 });

  useEffect(() => {
    fetchForms();
    // Atualizar a cada 10 segundos (opcional)
    const interval = setInterval(fetchForms, 10000);
    return () => clearInterval(interval);
  }, [testId]);

  const fetchForms = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(
        `/physical-tests/test/${testId}/forms`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const formsData = response.data.forms;
      setForms(formsData);
      
      // Calcular estatísticas
      const corrected = formsData.filter(f => f.is_corrected).length;
      setStats({
        total: formsData.length,
        corrected: corrected,
        pending: formsData.length - corrected
      });
      
      setLoading(false);
    } catch (error) {
      console.error('Erro ao buscar formulários:', error);
      setLoading(false);
    }
  };

  const progressPercent = stats.total > 0 
    ? ((stats.corrected / stats.total) * 100).toFixed(1)
    : 0;

  if (loading) return <div>Carregando...</div>;

  return (
    <div className="physical-test-forms">
      {/* Barra de Progresso */}
      <div className="progress-section">
        <h3>Progresso da Correção</h3>
        <div className="progress-bar-container">
          <div 
            className="progress-bar" 
            style={{ width: `${progressPercent}%` }}
          >
            {progressPercent}%
          </div>
        </div>
        <p>
          <strong>{stats.corrected}</strong> de <strong>{stats.total}</strong> cartões corrigidos
          ({stats.pending} pendentes)
        </p>
      </div>

      {/* Tabela de Formulários */}
      <table className="forms-table">
        <thead>
          <tr>
            <th>Aluno</th>
            <th>Status</th>
            <th>Corrigido em</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {forms.map(form => (
            <tr key={form.id}>
              <td>{form.student_name}</td>
              <td>
                {form.is_corrected ? (
                  <span className="badge badge-success">
                    ✅ Corrigido
                  </span>
                ) : (
                  <span className="badge badge-warning">
                    ⏳ Pendente
                  </span>
                )}
              </td>
              <td>
                {form.corrected_at ? (
                  new Date(form.corrected_at).toLocaleString('pt-BR')
                ) : (
                  '-'
                )}
              </td>
              <td>
                <button 
                  onClick={() => downloadPDF(form.id)}
                  disabled={!form.has_pdf_data}
                >
                  📄 Baixar PDF
                </button>
                {form.is_corrected && (
                  <button onClick={() => viewResult(form.student_id)}>
                    📊 Ver Resultado
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default PhysicalTestForms;
```

**CSS Exemplo:**
```css
.progress-section {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.progress-bar-container {
  width: 100%;
  height: 30px;
  background-color: #e9ecef;
  border-radius: 15px;
  overflow: hidden;
  margin: 15px 0;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #28a745, #20c997);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  transition: width 0.3s ease;
}

.badge {
  padding: 5px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: bold;
}

.badge-success {
  background-color: #28a745;
  color: white;
}

.badge-warning {
  background-color: #ffc107;
  color: #212529;
}

.forms-table {
  width: 100%;
  border-collapse: collapse;
}

.forms-table th,
.forms-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #dee2e6;
}

.forms-table th {
  background-color: #f8f9fa;
  font-weight: bold;
}

.forms-table tr:hover {
  background-color: #f8f9fa;
}
```

---

### **2️⃣ VUE.JS - Com Filtros**

```vue
<template>
  <div class="physical-test-forms">
    <!-- Barra de Progresso -->
    <div class="progress-section">
      <h3>Progresso da Correção</h3>
      <div class="progress-info">
        <span>{{ stats.corrected }} / {{ stats.total }} corrigidos</span>
        <span class="percentage">{{ progressPercent }}%</span>
      </div>
      <div class="progress-bar-container">
        <div 
          class="progress-bar" 
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
    </div>

    <!-- Filtros -->
    <div class="filters">
      <button 
        :class="{ active: filter === 'all' }"
        @click="filter = 'all'"
      >
        Todos ({{ stats.total }})
      </button>
      <button 
        :class="{ active: filter === 'corrected' }"
        @click="filter = 'corrected'"
      >
        ✅ Corrigidos ({{ stats.corrected }})
      </button>
      <button 
        :class="{ active: filter === 'pending' }"
        @click="filter = 'pending'"
      >
        ⏳ Pendentes ({{ stats.pending }})
      </button>
    </div>

    <!-- Lista de Formulários -->
    <div class="forms-grid">
      <div 
        v-for="form in filteredForms" 
        :key="form.id"
        class="form-card"
        :class="{ corrected: form.is_corrected }"
      >
        <div class="card-header">
          <h4>{{ form.student_name }}</h4>
          <span 
            class="badge"
            :class="form.is_corrected ? 'badge-success' : 'badge-warning'"
          >
            {{ form.is_corrected ? '✅ Corrigido' : '⏳ Pendente' }}
          </span>
        </div>
        
        <div class="card-body">
          <p v-if="form.corrected_at">
            <strong>Corrigido em:</strong><br>
            {{ formatDate(form.corrected_at) }}
          </p>
          <p v-else>
            <em>Aguardando correção...</em>
          </p>
        </div>
        
        <div class="card-actions">
          <button @click="downloadPDF(form.id)">
            📄 Baixar PDF
          </button>
          <button 
            v-if="form.is_corrected"
            @click="viewResult(form.student_id)"
          >
            📊 Ver Resultado
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  name: 'PhysicalTestForms',
  props: {
    testId: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      forms: [],
      filter: 'all', // 'all' | 'corrected' | 'pending'
      loading: true,
      refreshInterval: null
    };
  },
  computed: {
    stats() {
      const corrected = this.forms.filter(f => f.is_corrected).length;
      return {
        total: this.forms.length,
        corrected: corrected,
        pending: this.forms.length - corrected
      };
    },
    progressPercent() {
      return this.stats.total > 0 
        ? ((this.stats.corrected / this.stats.total) * 100).toFixed(1)
        : 0;
    },
    filteredForms() {
      if (this.filter === 'corrected') {
        return this.forms.filter(f => f.is_corrected);
      }
      if (this.filter === 'pending') {
        return this.forms.filter(f => !f.is_corrected);
      }
      return this.forms;
    }
  },
  mounted() {
    this.fetchForms();
    // Auto-refresh a cada 10 segundos
    this.refreshInterval = setInterval(this.fetchForms, 10000);
  },
  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  },
  methods: {
    async fetchForms() {
      try {
        const token = localStorage.getItem('token');
        const response = await axios.get(
          `/physical-tests/test/${this.testId}/forms`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        this.forms = response.data.forms;
        this.loading = false;
      } catch (error) {
        console.error('Erro ao buscar formulários:', error);
        this.loading = false;
      }
    },
    formatDate(dateString) {
      if (!dateString) return '-';
      return new Date(dateString).toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    },
    downloadPDF(formId) {
      // Implementar download
      window.open(`/physical-tests/test/${this.testId}/download/${formId}`, '_blank');
    },
    viewResult(studentId) {
      // Navegar para página de resultado
      this.$router.push(`/test/${this.testId}/result/${studentId}`);
    }
  }
};
</script>

<style scoped>
.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filters button {
  padding: 10px 20px;
  border: 2px solid #dee2e6;
  background: white;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.filters button.active {
  background: #007bff;
  color: white;
  border-color: #007bff;
}

.forms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.form-card {
  border: 2px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  background: white;
  transition: all 0.2s;
}

.form-card.corrected {
  border-color: #28a745;
  background: #f8fff9;
}

.form-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.card-actions {
  display: flex;
  gap: 10px;
  margin-top: 15px;
}

.card-actions button {
  flex: 1;
  padding: 8px;
  border: none;
  background: #007bff;
  color: white;
  border-radius: 4px;
  cursor: pointer;
}
</style>
```

---

### **3️⃣ VANILLA JAVASCRIPT - Simples e Direto**

```javascript
// Configuração
const API_BASE = 'https://sua-api.com';
const testId = 'test-uuid-aqui';

// Buscar formulários
async function loadForms() {
  const token = localStorage.getItem('token');
  
  try {
    const response = await fetch(
      `${API_BASE}/physical-tests/test/${testId}/forms`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error('Erro ao buscar formulários');
    }
    
    const data = await response.json();
    displayForms(data.forms);
    displayStats(data.forms);
    
  } catch (error) {
    console.error('Erro:', error);
    document.getElementById('forms-container').innerHTML = 
      '<p class="error">Erro ao carregar formulários</p>';
  }
}

// Exibir estatísticas
function displayStats(forms) {
  const total = forms.length;
  const corrected = forms.filter(f => f.is_corrected).length;
  const pending = total - corrected;
  const percentage = total > 0 ? ((corrected / total) * 100).toFixed(1) : 0;
  
  const statsHTML = `
    <div class="stats">
      <h3>Progresso da Correção</h3>
      <div class="progress-bar-container">
        <div class="progress-bar" style="width: ${percentage}%">
          ${percentage}%
        </div>
      </div>
      <p>
        <strong>${corrected}</strong> de <strong>${total}</strong> corrigidos
        (${pending} pendentes)
      </p>
    </div>
  `;
  
  document.getElementById('stats-container').innerHTML = statsHTML;
}

// Exibir formulários
function displayForms(forms) {
  const container = document.getElementById('forms-container');
  
  if (forms.length === 0) {
    container.innerHTML = '<p>Nenhum formulário encontrado</p>';
    return;
  }
  
  const formsHTML = forms.map(form => {
    const statusBadge = form.is_corrected
      ? '<span class="badge badge-success">✅ Corrigido</span>'
      : '<span class="badge badge-warning">⏳ Pendente</span>';
    
    const correctedDate = form.corrected_at
      ? new Date(form.corrected_at).toLocaleString('pt-BR')
      : '-';
    
    const resultButton = form.is_corrected
      ? `<button onclick="viewResult('${form.student_id}')">📊 Ver Resultado</button>`
      : '';
    
    return `
      <div class="form-card ${form.is_corrected ? 'corrected' : ''}">
        <div class="card-header">
          <h4>${form.student_name}</h4>
          ${statusBadge}
        </div>
        <div class="card-body">
          <p><strong>Status:</strong> ${form.status}</p>
          <p><strong>Corrigido em:</strong> ${correctedDate}</p>
        </div>
        <div class="card-actions">
          <button onclick="downloadPDF('${form.id}')">📄 Baixar PDF</button>
          ${resultButton}
        </div>
      </div>
    `;
  }).join('');
  
  container.innerHTML = formsHTML;
}

// Funções auxiliares
function downloadPDF(formId) {
  window.open(`${API_BASE}/physical-tests/test/${testId}/download/${formId}`, '_blank');
}

function viewResult(studentId) {
  window.location.href = `/test/${testId}/result/${studentId}`;
}

// Auto-refresh a cada 10 segundos
setInterval(loadForms, 10000);

// Carregar ao iniciar
document.addEventListener('DOMContentLoaded', loadForms);
```

**HTML:**
```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Formulários Físicos</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="container">
    <h1>Cartões Físicos da Prova</h1>
    
    <!-- Estatísticas -->
    <div id="stats-container"></div>
    
    <!-- Formulários -->
    <div id="forms-container" class="forms-grid"></div>
  </div>
  
  <script src="forms.js"></script>
</body>
</html>
```

---

## 📊 **DADOS DISPONÍVEIS NA RESPOSTA:**

### **Campos Principais:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | String (UUID) | ID único do formulário |
| `student_id` | String (UUID) | ID do aluno |
| `student_name` | String | Nome do aluno |
| `test_id` | String (UUID) | ID da prova |
| `class_test_id` | String (UUID) | ID da aplicação da prova na turma |
| **`status`** | **String** | **"gerado", "corrigido", "processado"** |
| **`is_corrected`** | **Boolean** | **Se foi corrigido (True/False)** |
| **`corrected_at`** | **String (ISO 8601)** | **Data/hora da correção** |
| `generated_at` | String (ISO 8601) | Data/hora de geração |
| `answer_sheet_sent_at` | String (ISO 8601) | Data/hora de envio |
| `qr_code_data` | String | Dados do QR Code |
| `has_pdf_data` | Boolean | Se tem PDF salvo |
| `has_answer_sheet_data` | Boolean | Se tem gabarito salvo |
| `has_correction_data` | Boolean | Se tem imagem de correção |

---

## 🎨 **EXEMPLOS DE UI/UX:**

### **1. Dashboard Resumido:**
```
┌─────────────────────────────────────────────────────────┐
│ CARTÕES FÍSICOS - PROVA DE MATEMÁTICA                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Progresso: 23/45 corrigidos (51.1%)                   │
│  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░         │
│                                                         │
│  ✅ Corrigidos: 23    ⏳ Pendentes: 22                  │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ [Todos (45)] [✅ Corrigidos (23)] [⏳ Pendentes (22)]  │
└─────────────────────────────────────────────────────────┘
```

### **2. Lista Detalhada:**
```
┌──────────────┬────────────┬──────────────────┬─────────┐
│ Aluno        │ Status     │ Corrigido em     │ Ações   │
├──────────────┼────────────┼──────────────────┼─────────┤
│ Ana Silva    │ ✅ Corrigido│ 22/01 às 14:30  │ [PDF]   │
│ João Santos  │ ⏳ Pendente │ -                │ [PDF]   │
│ Maria Costa  │ ✅ Corrigido│ 22/01 às 14:32  │ [PDF]   │
└──────────────┴────────────┴──────────────────┴─────────┘
```

---

## 🔔 **NOTIFICAÇÕES EM TEMPO REAL (OPCIONAL):**

Se você quiser notificar o professor quando um novo cartão for corrigido:

```javascript
// Usando WebSocket (se implementado no backend)
const ws = new WebSocket('ws://sua-api.com/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'form_corrected') {
    // Atualizar UI
    showNotification(`✅ Cartão de ${data.student_name} foi corrigido!`);
    loadForms(); // Recarregar lista
  }
};

// Ou usando polling (mais simples)
let lastCorrectedCount = 0;

setInterval(async () => {
  const data = await fetchForms();
  const currentCount = data.forms.filter(f => f.is_corrected).length;
  
  if (currentCount > lastCorrectedCount) {
    const diff = currentCount - lastCorrectedCount;
    showNotification(`✅ ${diff} novo(s) cartão(ões) corrigido(s)!`);
  }
  
  lastCorrectedCount = currentCount;
}, 5000); // Verificar a cada 5 segundos
```

---

## 🧪 **TESTANDO NO FRONTEND:**

### **1. Testar API diretamente no console do navegador:**

```javascript
// No console do navegador (F12)
const token = localStorage.getItem('token');
const testId = 'seu-test-id-aqui';

fetch(`/physical-tests/test/${testId}/forms`, {
  headers: { 'Authorization': `Bearer ${token}` }
})
  .then(r => r.json())
  .then(data => {
    console.log('Total de formulários:', data.total);
    console.log('Corrigidos:', data.forms.filter(f => f.is_corrected).length);
    console.table(data.forms);
  });
```

---

## ✅ **CHECKLIST PARA O FRONTEND:**

- [ ] Implementar chamada à API `/physical-tests/test/<test_id>/forms`
- [ ] Exibir lista de formulários com nome do aluno
- [ ] Mostrar badge de status (✅ Corrigido / ⏳ Pendente)
- [ ] Exibir data/hora de correção (se disponível)
- [ ] Implementar barra de progresso (X de Y corrigidos)
- [ ] Adicionar filtros (Todos / Corrigidos / Pendentes)
- [ ] Implementar auto-refresh (opcional, mas recomendado)
- [ ] Adicionar botão para baixar PDF
- [ ] Adicionar botão para ver resultado (se corrigido)
- [ ] Adicionar notificações de novos cartões corrigidos (opcional)

---

## 🎯 **NADA PRECISA SER ALTERADO:**

✅ **A API já está funcionando!**
✅ **Não é necessário alterar nenhuma chamada existente!**
✅ **Os campos novos (`is_corrected`, `corrected_at`, `status`) já estão na resposta!**

**Você só precisa:**
1. Usar os campos na interface
2. Exibir o status visualmente
3. Implementar filtros/estatísticas (opcional)

---

## 📚 **DOCUMENTAÇÃO DE REFERÊNCIA:**

- API Endpoint: `GET /physical-tests/test/<test_id>/forms`
- Modelo: `PhysicalTestForm` (`app/models/physicalTestForm.py`)
- Pipeline OMR: `correction_new_grid.py` (já atualizado)

---

## 🚀 **PRONTO PARA USO!**

Implemente qualquer um dos exemplos acima e terá uma interface completa para rastreamento de correções em tempo real! 🎉
