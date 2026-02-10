# Plano de Implementação - Frontend (Sistema de Competições)

Plano de implementação focado no frontend do sistema de competições.

---

## Índice

1. [Etapa 1: Sistema de Moedas](#etapa-1-sistema-de-moedas-frontend)
2. [Etapa 2: Competições CRUD (Admin)](#etapa-2-competições-crud-admin)
3. [Etapa 3: Listagem e Inscrição (Aluno)](#etapa-3-listagem-e-inscrição-aluno)
4. [Etapa 4: Aplicação e Entrega](#etapa-4-aplicação-e-entrega)
5. [Etapa 5: Ranking](#etapa-5-ranking)
6. [Etapa 6: Templates](#etapa-6-templates-admin)
7. [Etapa 7: Funcionalidades Avançadas](#etapa-7-funcionalidades-avançadas)
8. [Checklist Final](#checklist-final-frontend)

---

## Etapa 1: Sistema de Moedas (Frontend)

### Objetivo
Criar componentes para exibir saldo e histórico de moedas.

### 1.1 Componente: CoinBalance (reutilizável)

**Arquivo**: `src/components/Coins/CoinBalance.tsx`

**Props**:
```typescript
interface CoinBalanceProps {
  studentId?: string;  // opcional, padrão: aluno logado
  size?: 'small' | 'medium' | 'large';
  showLabel?: boolean;
}
```

**Funcionalidades**:
- Busca saldo via API (`GET /coins/balance`)
- Exibe ícone de moeda + valor
- Tooltip com "Ver histórico"

**Implementação**:
```typescript
import React, { useEffect, useState } from 'react';
import { apiClient } from '@/services/api';
import { Coin } from '@/components/icons';

export const CoinBalance: React.FC<CoinBalanceProps> = ({ 
  studentId, 
  size = 'medium',
  showLabel = true 
}) => {
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchBalance = async () => {
      try {
        const params = studentId ? { student_id: studentId } : {};
        const { data } = await apiClient.get('/coins/balance', { params });
        setBalance(data.balance);
      } catch (error) {
        console.error('Erro ao buscar saldo:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchBalance();
  }, [studentId]);
  
  if (loading) return <div>Carregando...</div>;
  
  const sizeClasses = {
    small: 'text-sm',
    medium: 'text-base',
    large: 'text-2xl'
  };
  
  return (
    <div className={`coin-balance coin-balance--${size} flex items-center gap-2`}
         data-testid="coin-balance">
      <Coin className={sizeClasses[size]} />
      <span className={sizeClasses[size]}>{balance ?? 0}</span>
      {showLabel && <span className="text-gray-600">moedas</span>}
    </div>
  );
};
```

### 1.2 Página: CoinHistory

**Arquivo**: `src/pages/Student/CoinHistory.tsx`

**Rota**: `/student/coins/history`

**Componentes**:
- Header com saldo atual (CoinBalance grande)
- Filtros (período, tipo)
- Lista de transações
- Paginação

**Implementação**:
```typescript
import React, { useState, useEffect } from 'react';
import { CoinBalance } from '@/components/Coins/CoinBalance';
import { apiClient } from '@/services/api';

export const CoinHistory: React.FC = () => {
  const [transactions, setTransactions] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        const { data } = await apiClient.get('/coins/transactions');
        setTransactions(data.transactions);
      } catch (error) {
        console.error('Erro ao buscar histórico:', error);
      } finally {
        setLoading(false);
      }
    };
    
    fetchTransactions();
  }, []);
  
  const filteredTransactions = transactions.filter(t => {
    if (filter === 'all') return true;
    if (filter === 'participation') return t.reason === 'competition_participation';
    if (filter === 'ranking') return t.reason.startsWith('competition_rank_');
    return true;
  });
  
  return (
    <div className="coin-history">
      <header className="mb-6">
        <h1 className="text-3xl font-bold mb-4">Histórico de Moedas</h1>
        <CoinBalance size="large" />
      </header>
      
      <div className="filters mb-4">
        <label>Filtrar por tipo:</label>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">Todos</option>
          <option value="participation">Participação</option>
          <option value="ranking">Ranking</option>
        </select>
      </div>
      
      <div className="transactions-list">
        {loading ? (
          <div>Carregando...</div>
        ) : filteredTransactions.length === 0 ? (
          <div>Nenhuma transação ainda</div>
        ) : (
          filteredTransactions.map(transaction => (
            <div key={transaction.id} className="transaction-card">
              <div className="amount" style={{ color: transaction.amount > 0 ? 'green' : 'red' }}>
                {transaction.amount > 0 ? '+' : ''}{transaction.amount}
              </div>
              <div className="description">{transaction.description || transaction.reason}</div>
              <div className="date">{new Date(transaction.created_at).toLocaleDateString()}</div>
              <div className="balance-after">Saldo: {transaction.balance_after}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
```

### 1.3 Integração no Header

**Arquivo**: `src/components/Layout/StudentNavbar.tsx`

```typescript
import { CoinBalance } from '@/components/Coins/CoinBalance';

export const StudentNavbar: React.FC = () => {
  return (
    <nav>
      {/* ... outros itens do menu */}
      
      <div className="coin-balance-header">
        <CoinBalance size="small" showLabel={false} />
      </div>
    </nav>
  );
};
```

---

## Etapa 2: Competições CRUD (Admin)

### Objetivo
Criar interface de gerenciamento de competições para admin/coordenador.

### 2.1 Página: CompetitionList (Admin)

**Arquivo**: `src/pages/Admin/Competitions/CompetitionList.tsx`

**Rota**: `/admin/competitions`

**Componentes**:
- Header + botão "Nova Competição"
- Filtros (status, disciplina, nível)
- Tabela/Cards de competições
- Ações (Ver, Editar, Cancelar)

**Implementação**:
```typescript
export const CompetitionList: React.FC = () => {
  const [competitions, setCompetitions] = useState([]);
  const [filters, setFilters] = useState({ status: 'all' });
  
  useEffect(() => {
    fetchCompetitions();
  }, [filters]);
  
  const fetchCompetitions = async () => {
    const { data } = await apiClient.get('/competitions/', { params: filters });
    setCompetitions(data.competitions);
  };
  
  return (
    <div className="competition-list">
      <header>
        <h1>Competições</h1>
        <button onClick={() => setModalOpen(true)}>
          Nova Competição
        </button>
      </header>
      
      <div className="filters">
        {/* Filtros por status, disciplina, nível */}
      </div>
      
      <div className="competitions-grid">
        {competitions.map(comp => (
          <CompetitionCard key={comp.id} competition={comp} />
        ))}
      </div>
      
      <CreateCompetitionModal 
        open={modalOpen} 
        onClose={() => setModalOpen(false)}
        onSuccess={fetchCompetitions}
      />
    </div>
  );
};
```

### 2.2 Modal: CreateCompetitionModal

**Arquivo**: `src/pages/Admin/Competitions/CreateCompetitionModal.tsx`

**Etapas do formulário**:
1. Informações básicas (nome, disciplina, nível, escopo)
2. Datas (inscrição, aplicação)
3. Questões (modo, regras)
4. Recompensas (participação, ranking)
5. Avançado (critério ranking, visibilidade, limite)

**Endpoints para o campo Escopo (Etapa 1):**
- **Escopos permitidos para o usuário:** `GET /competitions/allowed-scopes` — retorna `{ "allowed_scopes": ["individual", "turma", ...] }`. Montar o select de “Escopo” **somente** com esses valores (cada perfil vê apenas o que pode usar: admin = todos; tec adm = individual, turma, escola, municipio; diretor/coordenador = individual, turma, escola; professor = individual, turma). Não há mais escopo "série".
- **Turma:** `GET /competitions/eligible-classes?level=1` ou `?level=2`. **Escola:** 1) `GET /city/states` 2) `GET /city/municipalities/state/<state>` 3) `GET /schools?city_id=<id>`. **Município:** 1) `GET /city/states` 2) `GET /city/municipalities/state/<state>`. **Estado:** `GET /city/states`. Enviar `scope` e `scope_filter` conforme plano de competições.

**Implementação** (resumida):
```typescript
export const CreateCompetitionModal: React.FC<Props> = ({ open, onClose, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    name: '',
    subject_id: '',
    level: 1,
    // ... outros campos
  });
  
  const [errors, setErrors] = useState({});
  
  const validate = () => {
    const newErrors = {};
    
    if (!formData.name) newErrors.name = 'Nome é obrigatório';
    if (!formData.subject_id) newErrors.subject_id = 'Disciplina é obrigatória';
    
    // Validar datas
    if (new Date(formData.application) <= new Date(formData.enrollment_end)) {
      newErrors.application = 'Data de aplicação deve ser após fim da inscrição';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async () => {
    if (!validate()) return;
    
    try {
      await apiClient.post('/competitions/', formData);
      onSuccess();
      onClose();
    } catch (error) {
      // Handle error
    }
  };
  
  return (
    <Modal open={open} onClose={onClose}>
      <div className="modal-content">
        <h2>Nova Competição</h2>
        
        {/* Stepper */}
        <Stepper activeStep={step} />
        
        {/* Etapa 1: Informações básicas */}
        {step === 1 && (
          <div>
            <input 
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              placeholder="Nome da competição"
            />
            {errors.name && <span className="error">{errors.name}</span>}
            
            {/* ... outros campos */}
          </div>
        )}
        
        {/* Outras etapas... */}
        
        <div className="modal-actions">
          {step > 1 && <button onClick={() => setStep(step - 1)}>Voltar</button>}
          {step < 5 && <button onClick={() => setStep(step + 1)}>Próximo</button>}
          {step === 5 && <button onClick={handleSubmit}>Criar Competição</button>}
        </div>
      </div>
    </Modal>
  );
};
```

---

## Etapa 3: Listagem e Inscrição (Aluno)

### Objetivo
Interface para alunos visualizarem e se inscreverem em competições.

### 3.1 Página: CompetitionListStudent

**Arquivo**: `src/pages/Student/Competitions/CompetitionListStudent.tsx`

**Rota**: `/student/competitions`

**Componentes**:
- Abas: Abertas, Próximas, Minhas Inscrições, Encerradas
- Cards de competição
- Modal de inscrição

**Implementação**:
```typescript
export const CompetitionListStudent: React.FC = () => {
  const [tab, setTab] = useState('abertas');
  const [competitions, setCompetitions] = useState([]);
  
  useEffect(() => {
    fetchCompetitions();
  }, [tab]);
  
  const fetchCompetitions = async () => {
    const { data } = await apiClient.get('/competitions/available');
    setCompetitions(data.competitions);
  };
  
  return (
    <div className="competition-list-student">
      <h1>Competições Disponíveis</h1>
      
      <Tabs value={tab} onChange={setTab}>
        <Tab value="abertas">Abertas</Tab>
        <Tab value="proximas">Próximas</Tab>
        <Tab value="minhas">Minhas Inscrições</Tab>
        <Tab value="encerradas">Encerradas</Tab>
      </Tabs>
      
      <div className="competitions-grid">
        {competitions.map(comp => (
          <CompetitionCardStudent 
            key={comp.id} 
            competition={comp}
            onEnroll={() => handleEnroll(comp.id)}
          />
        ))}
      </div>
    </div>
  );
};
```

### 3.2 Modal: EnrollConfirmationModal

**Arquivo**: `src/pages/Student/Competitions/EnrollConfirmationModal.tsx`

```typescript
export const EnrollConfirmationModal: React.FC<Props> = ({ 
  competition, 
  open, 
  onClose, 
  onConfirm 
}) => {
  const [loading, setLoading] = useState(false);
  
  const handleConfirm = async () => {
    setLoading(true);
    try {
      await apiClient.post(`/competitions/${competition.id}/enroll`);
      toast.success('Inscrição realizada com sucesso!');
      onConfirm();
      onClose();
    } catch (error) {
      toast.error('Erro ao se inscrever');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Modal open={open} onClose={onClose}>
      <h2>Confirmar Inscrição</h2>
      <p>Deseja se inscrever na competição <strong>{competition.name}</strong>?</p>
      
      <div className="competition-info">
        <p>Disciplina: {competition.subject.name}</p>
        <p>Período: {formatPeriod(competition)}</p>
        <p>Recompensas: {competition.reward_config.participation_coins} moedas</p>
      </div>
      
      <div className="modal-actions">
        <button onClick={onClose}>Cancelar</button>
        <button onClick={handleConfirm} disabled={loading}>
          {loading ? 'Inscrevendo...' : 'Confirmar Inscrição'}
        </button>
      </div>
    </Modal>
  );
};
```

---

## Etapa 4: Aplicação e Entrega

### Modal: CompetitionSubmitSuccessModal

**Arquivo**: `src/pages/Student/Competitions/CompetitionSubmitSuccessModal.tsx`

```typescript
export const CompetitionSubmitSuccessModal: React.FC<Props> = ({
  open,
  coinsEarned,
  competitionName,
  onClose
}) => {
  return (
    <Modal open={open} onClose={onClose}>
      <div className="success-modal">
        <CheckCircleIcon className="success-icon" />
        
        <h2>Prova Entregue com Sucesso!</h2>
        
        <div className="coins-earned" data-testid="coin-animation">
          <CoinIcon className="animate-pulse" />
          <span className="amount">+{coinsEarned} moedas!</span>
        </div>
        
        <p>Você ganhou {coinsEarned} moedas por participar!</p>
        <p>Fique de olho no ranking. Primeiros colocados ganham moedas extras!</p>
        
        <button onClick={onClose}>Voltar para Competições</button>
      </div>
    </Modal>
  );
};
```

---

## Etapa 5: Ranking

### Componente: CompetitionRanking

**Arquivo**: `src/pages/Student/Competitions/CompetitionRanking.tsx`

```typescript
export const CompetitionRanking: React.FC<Props> = ({ 
  competitionId,
  rankingVisibility 
}) => {
  const [ranking, setRanking] = useState([]);
  const [myPosition, setMyPosition] = useState(null);
  
  useEffect(() => {
    fetchRanking();
    
    // Auto-refresh se realtime
    if (rankingVisibility === 'realtime') {
      const interval = setInterval(fetchRanking, 10000); // 10s
      return () => clearInterval(interval);
    }
  }, [competitionId, rankingVisibility]);
  
  const fetchRanking = async () => {
    const { data } = await apiClient.get(`/competitions/${competitionId}/ranking`);
    setRanking(data.ranking);
    setMyPosition(data.my_position);
  };
  
  return (
    <div className="competition-ranking">
      <h2>Ranking</h2>
      
      {/* Minha posição (destaque) */}
      {myPosition && (
        <div className="my-position">
          <p>Você está em <strong>{myPosition.position}º lugar</strong> de {ranking.length} participantes</p>
          {myPosition.coins_earned > 0 && (
            <div className="prize-badge">
              Você ganhou {myPosition.coins_earned} moedas!
            </div>
          )}
        </div>
      )}
      
      {/* Podium (top 3) */}
      <div className="podium">
        {ranking.slice(0, 3).map((student, idx) => (
          <div key={student.student_id} className={`podium-position podium-${idx + 1}`}>
            <div className="medal" data-testid={`medal-${['gold', 'silver', 'bronze'][idx]}`}>
              {['🥇', '🥈', '🥉'][idx]}
            </div>
            <div className="student-name">{student.student_name}</div>
            <div className="score">{student.value}</div>
            {student.coins_earned && (
              <div className="coins">+{student.coins_earned} moedas</div>
            )}
          </div>
        ))}
      </div>
      
      {/* Lista completa */}
      <div className="ranking-list">
        {ranking.map(student => (
          <div key={student.student_id} className="ranking-item">
            <span className="position">{student.position}º</span>
            <span className="name">{student.student_name}</span>
            <span className="class">{student.student_class}</span>
            <span className="score">{student.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

---

## Checklist Final - Frontend

### Etapa 1: Sistema de Moedas
- [ ] Implementar CoinBalance
- [ ] Implementar CoinHistory
- [ ] Integrar no header (StudentNavbar)

### Etapa 2: Competições CRUD
- [ ] Implementar CompetitionList (Admin)
- [ ] Implementar CreateCompetitionModal

### Etapa 3: Inscrição
- [ ] Implementar CompetitionListStudent
- [ ] Implementar EnrollConfirmationModal

### Etapa 4: Aplicação
- [ ] Implementar CompetitionSubmitSuccessModal

### Etapa 5: Ranking
- [ ] Implementar CompetitionRanking (pódio e lista)

### Etapa 6: Templates
- [ ] Implementar UI de CRUD de templates

### Etapa 7: Avançadas
- [ ] Implementar analytics e funcionalidades avançadas
