// Exemplo de implementação do cronômetro no frontend
// Este arquivo demonstra como o frontend pode gerenciar o tempo da avaliação

class TestTimer {
    constructor(testId, sessionId, timeLimitMinutes, startedAt) {
        this.testId = testId;
        this.sessionId = sessionId;
        this.timeLimitMinutes = timeLimitMinutes;
        this.startedAt = new Date(startedAt);
        this.interval = null;
        this.onTimeUpdate = null;
        this.onTimeExpired = null;
        
        // Calcular tempo inicial
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
        // Atualizar a cada segundo
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
            
            // Se expirou, parar o cronômetro
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
    
    getTimeInfo() {
        return {
            elapsedMinutes: this.elapsedMinutes,
            remainingMinutes: this.remainingMinutes,
            isExpired: this.isExpired,
            formattedTime: this.formatTime()
        };
    }
}

// Exemplo de uso com React/Vue/Angular
class TestSessionManager {
    constructor() {
        this.timer = null;
        this.currentSession = null;
    }
    
    async startTestSession(testId) {
        try {
            // 1. Iniciar sessão no backend
            const response = await fetch(`/api/test/${testId}/start-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });
            
            const sessionData = await response.json();
            
            if (response.ok) {
                this.currentSession = sessionData;
                
                // 2. Iniciar cronômetro no frontend
                this.timer = new TestTimer(
                    testId,
                    sessionData.session_id,
                    sessionData.time_limit_minutes,
                    sessionData.started_at
                );
                
                // 3. Configurar callbacks
                this.timer.onTimeUpdate = (timeInfo) => {
                    this.updateTimerDisplay(timeInfo);
                };
                
                this.timer.onTimeExpired = () => {
                    this.handleTimeExpired();
                };
                
                // 4. Iniciar cronômetro
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
    
    async getSessionInfo(testId) {
        try {
            const response = await fetch(`/api/test/${testId}/session-info`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
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
            console.error('Erro ao obter informações da sessão:', error);
            return null;
        }
    }
    
    updateTimerDisplay(timeInfo) {
        // Atualizar interface do usuário
        const timerElement = document.getElementById('test-timer');
        if (timerElement) {
            timerElement.textContent = timeInfo.formattedTime;
            
            // Mudar cor quando estiver acabando o tempo
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
    
    async submitAnswers(answers) {
        try {
            const response = await fetch(`/api/test/${this.currentSession.test_id}/submit`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify({
                    session_id: this.currentSession.session_id,
                    answers: answers
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
        // Mostrar resultados para o usuário
        console.log('Resultados:', result);
        // Implementar lógica para mostrar resultados
    }
}

// Exemplo de uso
const testManager = new TestSessionManager();

// Iniciar teste
async function startTest(testId) {
    try {
        const session = await testManager.startTestSession(testId);
        console.log('Sessão iniciada:', session);
    } catch (error) {
        console.error('Erro ao iniciar teste:', error);
    }
}

// Verificar sessão existente
async function checkExistingSession(testId) {
    const sessionInfo = await testManager.getSessionInfo(testId);
    if (sessionInfo) {
        console.log('Sessão existente encontrada:', sessionInfo);
    }
} 