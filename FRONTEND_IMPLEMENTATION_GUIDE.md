# Guia de Implementação Frontend - Sistema de Cronômetro

## 📋 Resumo da Mudança

O backend foi simplificado para deixar o **frontend responsável pelo controle do cronômetro**. Agora o frontend calcula o tempo decorrido/restante baseado no `started_at` fornecido pelo backend.

## 🔄 Mudanças Principais

### Antes (Backend Controlava Tudo)
- Backend calculava `remaining_time_minutes` em tempo real
- Validação de tempo no backend
- Frontend apenas exibia o tempo

### Agora (Frontend Controla Cronômetro)
- Backend fornece `started_at` e `time_limit_minutes`
- Frontend calcula tempo decorrido/restante
- Frontend controla quando o tempo expira
- Auto-submissão quando tempo acaba

## 🚀 Implementação Frontend

### 1. Classe TestTimer

```javascript
class TestTimer {
    constructor(testId, sessionId, timeLimitMinutes, startedAt) {
        this.testId = testId;
        this.sessionId = sessionId;
        this.timeLimitMinutes = timeLimitMinutes;
        this.startedAt = new Date(startedAt);
        this.interval = null;
        this.onTimeUpdate = null;
        this.onTimeExpired = null;
        
        this.calculateTime();
    }
    
    calculateTime() {
        const now = new Date();
        const elapsedMs = now - this.startedAt;
        this.elapsedMinutes = Math.floor(elapsedMs / (1000 * 60));
        this.remainingMinutes = Math.max(0, this.timeLimitMinutes - this.elapsedMinutes);
        this.isExpired = this.remainingMinutes <= 0;
    }
    
    start() {
        this.interval = setInterval(() => {
            this.calculateTime();
            
            if (this.onTimeUpdate) {
                this.onTimeUpdate({
                    elapsedMinutes: this.elapsedMinutes,
                    remainingMinutes: this.remainingMinutes,
                    isExpired: this.isExpired,
                    formattedTime: this.formatTime()
                });
            }
            
            if (this.isExpired) {
                this.stop();
                if (this.onTimeExpired) {
                    this.onTimeExpired();
                }
            }
        }, 1000);
        
        // Executar imediatamente
        this.calculateTime();
        if (this.onTimeUpdate) {
            this.onTimeUpdate({
                elapsedMinutes: this.elapsedMinutes,
                remainingMinutes: this.remainingMinutes,
                isExpired: this.isExpired,
                formattedTime: this.formatTime()
            });
        }
    }
    
    stop() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }
    
    formatTime() {
        const hours = Math.floor(this.remainingMinutes / 60);
        const minutes = this.remainingMinutes % 60;
        const seconds = Math.floor((this.timeLimitMinutes * 60 - this.elapsedMinutes * 60) % 60);
        
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
}
```

### 2. Gerenciador de Sessão

```javascript
class TestSessionManager {
    constructor() {
        this.timer = null;
        this.currentSession = null;
        this.answers = [];
    }
    
    async startTestSession(testId) {
        try {
            const response = await fetch(`/api/test/${testId}/start-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getToken()}`
                }
            });
            
            const sessionData = await response.json();
            
            if (response.ok) {
                this.currentSession = sessionData;
                
                // Iniciar cronômetro
                this.timer = new TestTimer(
                    testId,
                    sessionData.session_id,
                    sessionData.time_limit_minutes,
                    sessionData.started_at
                );
                
                // Configurar callbacks
                this.timer.onTimeUpdate = (timeInfo) => {
                    this.updateTimerDisplay(timeInfo);
                };
                
                this.timer.onTimeExpired = () => {
                    this.handleTimeExpired();
                };
                
                this.timer.start();
                
                return sessionData;
            } else {
                throw new Error(sessionData.error);
            }
        } catch (error) {
            console.error('Erro ao iniciar sessão:', error);
            throw error;
        }
    }
    
    async checkExistingSession(testId) {
        try {
            const response = await fetch(`/api/test/${testId}/session-info`, {
                headers: {
                    'Authorization': `Bearer ${this.getToken()}`
                }
            });
            
            const sessionInfo = await response.json();
            
            if (response.ok && sessionInfo.session_exists) {
                // Recriar timer com dados existentes
                this.timer = new TestTimer(
                    testId,
                    sessionInfo.session_id,
                    sessionInfo.time_limit_minutes,
                    sessionInfo.started_at
                );
                
                this.timer.onTimeUpdate = (timeInfo) => {
                    this.updateTimerDisplay(timeInfo);
                };
                
                this.timer.onTimeExpired = () => {
                    this.handleTimeExpired();
                };
                
                this.timer.start();
                
                return sessionInfo;
            }
            
            return null;
        } catch (error) {
            console.error('Erro ao verificar sessão existente:', error);
            return null;
        }
    }
    
    updateTimerDisplay(timeInfo) {
        // Atualizar interface do usuário
        const timerElement = document.getElementById('test-timer');
        if (timerElement) {
            timerElement.textContent = timeInfo.formattedTime;
            
            // Mudar cor quando estiver acabando o tempo
            timerElement.classList.remove('warning', 'expired');
            
            if (timeInfo.remainingMinutes <= 5) {
                timerElement.classList.add('warning');
            }
            if (timeInfo.isExpired) {
                timerElement.classList.add('expired');
            }
        }
    }
    
    handleTimeExpired() {
        // Auto-submeter quando o tempo expirar
        alert('Tempo esgotado! Suas respostas serão enviadas automaticamente.');
        this.submitAnswers();
    }
    
    async submitAnswers(answers = null) {
        try {
            const answersToSubmit = answers || this.answers;
            
            const response = await fetch(`/api/test/${this.currentSession.test_id}/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getToken()}`
                },
                body: JSON.stringify({
                    session_id: this.currentSession.session_id,
                    answers: answersToSubmit
                })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                // Parar cronômetro
                if (this.timer) {
                    this.timer.stop();
                }
                
                // Mostrar resultados
                this.showResults(result);
                
                return result;
            } else {
                throw new Error(result.error);
            }
        } catch (error) {
            console.error('Erro ao submeter respostas:', error);
            throw error;
        }
    }
    
    showResults(result) {
        // Implementar lógica para mostrar resultados
        console.log('Resultados:', result);
        // Exibir modal ou página com resultados
    }
    
    getToken() {
        return localStorage.getItem('token') || sessionStorage.getItem('token');
    }
}
```

## 📡 Rotas da API

### 1. Iniciar Sessão
```http
POST /api/test/{test_id}/start-session
Authorization: Bearer {token}
```

**Resposta:**
```json
{
  "message": "Sessão iniciada com sucesso",
  "session_id": "uuid",
  "started_at": "2024-01-01T10:00:00",
  "time_limit_minutes": 60
}
```

### 2. Verificar Sessão Existente
```http
GET /api/test/{test_id}/session-info
Authorization: Bearer {token}
```

**Resposta:**
```json
{
  "session_id": "uuid",
  "started_at": "2024-01-01T10:00:00",
  "time_limit_minutes": 60,
  "elapsed_minutes": 30,
  "remaining_minutes": 30,
  "is_expired": false,
  "session_exists": true
}
```

### 3. Submeter Respostas
```http
POST /api/test/{test_id}/submit
Authorization: Bearer {token}
Content-Type: application/json

{
  "session_id": "uuid",
  "answers": [
    {
      "question_id": "uuid",
      "answer": "resposta_do_aluno"
    }
  ]
}
```

**Resposta:**
```json
{
  "message": "Respostas submetidas com sucesso",
  "session_id": "uuid",
  "submitted_at": "2024-01-01T11:00:00",
  "duration_minutes": 60,
  "results": {
    "total_questions": 10,
    "correct_answers": 8,
    "score_percentage": 80.0,
    "grade": 8.0,
    "answers_saved": 10
  }
}
```

## 🎨 Exemplo de Interface

### HTML
```html
<div class="test-container">
  <div class="test-header">
    <h1>Teste de Matemática</h1>
    <div id="test-timer" class="timer">01:00:00</div>
  </div>
  
  <div class="test-content">
    <!-- Questões aqui -->
  </div>
  
  <div class="test-footer">
    <button id="submit-test" onclick="submitTest()">Enviar Respostas</button>
  </div>
</div>
```

### CSS
```css
.timer {
  font-size: 1.5rem;
  font-weight: bold;
  padding: 10px;
  border-radius: 5px;
  background: #f0f0f0;
}

.timer.warning {
  background: #fff3cd;
  color: #856404;
  animation: pulse 1s infinite;
}

.timer.expired {
  background: #f8d7da;
  color: #721c24;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}
```

## 🔄 Fluxo de Implementação

### 1. Inicialização da Página
```javascript
// Ao carregar a página do teste
async function initializeTest(testId) {
    const testManager = new TestSessionManager();
    
    try {
        // Verificar se já existe uma sessão
        const existingSession = await testManager.checkExistingSession(testId);
        
        if (existingSession) {
            console.log('Sessão existente encontrada:', existingSession);
            // Continuar com a sessão existente
        } else {
            // Iniciar nova sessão
            const newSession = await testManager.startTestSession(testId);
            console.log('Nova sessão iniciada:', newSession);
        }
        
        // Carregar questões do teste
        await loadTestQuestions(testId);
        
    } catch (error) {
        console.error('Erro ao inicializar teste:', error);
        alert('Erro ao carregar o teste. Tente novamente.');
    }
}
```

### 2. Gerenciamento de Respostas
```javascript
// Salvar resposta do aluno
function saveAnswer(questionId, answer) {
    testManager.answers.push({
        question_id: questionId,
        answer: answer
    });
    
    // Opcional: Salvar no localStorage para recuperação
    localStorage.setItem(`test_${testId}_answers`, JSON.stringify(testManager.answers));
}

// Submeter teste
async function submitTest() {
    try {
        const result = await testManager.submitAnswers();
        console.log('Teste enviado com sucesso:', result);
        
        // Redirecionar para página de resultados
        window.location.href = `/results/${result.session_id}`;
        
    } catch (error) {
        console.error('Erro ao enviar teste:', error);
        alert('Erro ao enviar respostas. Tente novamente.');
    }
}
```

### 3. Recuperação de Sessão
```javascript
// Recuperar respostas salvas
function loadSavedAnswers(testId) {
    const savedAnswers = localStorage.getItem(`test_${testId}_answers`);
    if (savedAnswers) {
        testManager.answers = JSON.parse(savedAnswers);
        return testManager.answers;
    }
    return [];
}

// Limpar dados salvos
function clearSavedAnswers(testId) {
    localStorage.removeItem(`test_${testId}_answers`);
}
```

## ⚠️ Considerações Importantes

### 1. Sincronização de Tempo
- O frontend calcula o tempo baseado no `started_at` do servidor
- Se o relógio do cliente estiver errado, pode haver discrepâncias
- Considere sincronizar o tempo com o servidor periodicamente

### 2. Recuperação de Sessão
- Salve respostas no localStorage para recuperação
- Verifique sessão existente ao carregar a página
- Permita continuar de onde parou

### 3. Tratamento de Erros
- Implemente retry automático para falhas de rede
- Mostre mensagens claras de erro
- Permita salvar respostas localmente

### 4. Acessibilidade
- Use cores contrastantes para o cronômetro
- Adicione alertas sonoros quando tempo estiver acabando
- Implemente navegação por teclado

## 🧪 Testes Recomendados

1. **Teste de Tempo Normal**
   - Iniciar teste e aguardar tempo normal
   - Verificar se cronômetro funciona corretamente

2. **Teste de Expiração**
   - Iniciar teste e aguardar expirar
   - Verificar se auto-submissão funciona

3. **Teste de Recuperação**
   - Iniciar teste, fechar navegador, reabrir
   - Verificar se recupera sessão corretamente

4. **Teste de Rede**
   - Simular falhas de rede
   - Verificar se respostas são salvas localmente

## 📱 Responsividade

```css
/* Mobile */
@media (max-width: 768px) {
    .timer {
        font-size: 1.2rem;
        padding: 8px;
    }
    
    .test-header {
        flex-direction: column;
        gap: 10px;
    }
}
```

## 🚀 Próximos Passos

1. **Implementar** a classe `TestTimer`
2. **Criar** o `TestSessionManager`
3. **Integrar** com a interface existente
4. **Testar** todos os cenários
5. **Otimizar** performance e UX

Esta implementação garante uma experiência de usuário fluida e confiável, com o frontend controlando completamente o cronômetro enquanto mantém sincronização com o backend. 