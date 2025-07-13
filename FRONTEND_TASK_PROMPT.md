# 🎯 TASK: Implementar Nova Abordagem do Cronômetro

## 📋 Contexto

O backend foi **simplificado** para deixar o frontend responsável pelo controle do cronômetro. Agora você precisa implementar o cálculo de tempo no frontend.

## 🔄 Mudanças no Backend

### ❌ Removido do Backend:
- Cálculo de `remaining_time_minutes` em tempo real
- Validação de tempo no backend
- Campo `actual_start_time` (removido)

### ✅ Mantido no Backend:
- `started_at` - Quando a sessão iniciou
- `time_limit_minutes` - Tempo limite do teste
- `submitted_at` - Quando foi finalizado

## 🚀 O que Você Precisa Implementar

### 1. Classe TestTimer
```javascript
class TestTimer {
    constructor(testId, sessionId, timeLimitMinutes, startedAt) {
        // Inicializar com dados do backend
        this.startedAt = new Date(startedAt);
        this.timeLimitMinutes = timeLimitMinutes;
        // ... resto da implementação
    }
    
    calculateTime() {
        // Calcular tempo decorrido e restante
        const now = new Date();
        const elapsedMs = now - this.startedAt;
        this.elapsedMinutes = Math.floor(elapsedMs / (1000 * 60));
        this.remainingMinutes = Math.max(0, this.timeLimitMinutes - this.elapsedMinutes);
        this.isExpired = this.remainingMinutes <= 0;
    }
    
    start() {
        // Iniciar cronômetro que atualiza a cada segundo
        // Chamar onTimeUpdate e onTimeExpired quando necessário
    }
}
```

### 2. Gerenciador de Sessão
```javascript
class TestSessionManager {
    async startTestSession(testId) {
        // POST /api/test/{test_id}/start-session
        // Criar TestTimer com dados retornados
    }
    
    async checkExistingSession(testId) {
        // GET /api/test/{test_id}/session-info
        // Recriar TestTimer se sessão existir
    }
    
    async submitAnswers(answers) {
        // POST /api/test/{test_id}/submit
        // Enviar respostas e parar cronômetro
    }
}
```

## 📡 Rotas que Você Precisa Usar

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

## 🎨 Interface que Você Precisa Criar

### HTML
```html
<div class="test-container">
  <div class="test-header">
    <h1>Teste de Matemática</h1>
    <div id="test-timer" class="timer">01:00:00</div>
  </div>
  
  <div class="test-content">
    <!-- Suas questões aqui -->
  </div>
  
  <div class="test-footer">
    <button id="submit-test">Enviar Respostas</button>
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
```

## 🔄 Fluxo de Implementação

### 1. Ao Carregar a Página do Teste
```javascript
// Verificar se já existe uma sessão
const existingSession = await testManager.checkExistingSession(testId);

if (existingSession) {
    // Continuar com sessão existente
    console.log('Sessão existente encontrada');
} else {
    // Iniciar nova sessão
    const newSession = await testManager.startTestSession(testId);
    console.log('Nova sessão iniciada');
}
```

### 2. Atualizar Interface do Cronômetro
```javascript
timer.onTimeUpdate = (timeInfo) => {
    const timerElement = document.getElementById('test-timer');
    timerElement.textContent = timeInfo.formattedTime;
    
    // Mudar cor quando estiver acabando o tempo
    if (timeInfo.remainingMinutes <= 5) {
        timerElement.classList.add('warning');
    }
    if (timeInfo.isExpired) {
        timerElement.classList.add('expired');
    }
};
```

### 3. Auto-submissão quando Tempo Expirar
```javascript
timer.onTimeExpired = () => {
    alert('Tempo esgotado! Suas respostas serão enviadas automaticamente.');
    testManager.submitAnswers();
};
```

## ⚠️ Pontos Importantes

### 1. Sincronização de Tempo
- O frontend calcula baseado no `started_at` do servidor
- Se o relógio do cliente estiver errado, pode haver discrepâncias
- Considere sincronizar periodicamente

### 2. Recuperação de Sessão
- Salve respostas no localStorage
- Verifique sessão existente ao carregar página
- Permita continuar de onde parou

### 3. Tratamento de Erros
- Implemente retry para falhas de rede
- Mostre mensagens claras de erro
- Salve respostas localmente

## 🧪 Testes que Você Precisa Fazer

1. **Teste Normal**: Iniciar teste e aguardar tempo normal
2. **Teste de Expiração**: Aguardar tempo expirar e verificar auto-submissão
3. **Teste de Recuperação**: Fechar navegador e reabrir
4. **Teste de Rede**: Simular falhas de rede

## 📱 Responsividade

```css
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

## 🎯 Entregáveis Esperados

1. ✅ **Classe TestTimer** funcionando
2. ✅ **TestSessionManager** implementado
3. ✅ **Interface do cronômetro** atualizada
4. ✅ **Auto-submissão** quando tempo expira
5. ✅ **Recuperação de sessão** funcionando
6. ✅ **Testes** passando

## 📞 Suporte

Se tiver dúvidas sobre:
- Rotas da API: Consulte o guia completo
- Implementação: Use o exemplo fornecido
- Testes: Execute todos os cenários listados

## 🚀 Próximos Passos

1. **Implementar** a classe `TestTimer`
2. **Criar** o `TestSessionManager`
3. **Integrar** com sua interface existente
4. **Testar** todos os cenários
5. **Deploy** e monitoramento

---

**💡 Dica**: Use o arquivo `frontend_timer_example.js` como referência completa para a implementação! 