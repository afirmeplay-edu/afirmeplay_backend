# Plano de Implementação - Sistema de Competições

**Este documento foi dividido em dois planos separados para melhor organização:**

- **📘 Backend**: [PLANO_IMPLEMENTACAO_BACKEND.md](./PLANO_IMPLEMENTACAO_BACKEND.md)
- **📗 Frontend**: [PLANO_IMPLEMENTACAO_FRONTEND.md](./PLANO_IMPLEMENTACAO_FRONTEND.md)

---

## Visão Geral Consolidada

Este documento consolida a visão geral do projeto. Para detalhes de implementação, consulte os planos específicos de backend e frontend.

---

## Visão geral das etapas

| Etapa | Descrição | Dependências |
|-------|-----------|--------------|
| 1 | Sistema de Moedas (base) | Nenhuma |
| 2 | Competições CRUD (estrutura básica) | Etapa 1 |
| 3 | Inscrição e Listagem | Etapa 2 |
| 4 | Aplicação e Entrega (integração com prova) | Etapa 3 |
| 5 | Ranking e Pagamento de Recompensas | Etapa 4 |
| 6 | Templates e Criação Automática | Etapa 5 |
| 7 | Funcionalidades Avançadas | Etapa 6 |

---

## Metodologia: Test-Driven Development (TDD)

### Processo TDD

Para cada funcionalidade implementada, seguir o ciclo **Red-Green-Refactor**:

1. **🔴 Red (Teste Falhando)**
   - Escrever teste primeiro (antes do código)
   - Rodar teste e verificar que falha (comportamento esperado)
   - Confirmar que o teste está testando o que deveria

2. **🟢 Green (Fazer Passar)**
   - Implementar o código mínimo necessário para fazer o teste passar
   - Não se preocupar com otimização nesta fase
   - Rodar teste novamente e verificar que passa

3. **🔵 Refactor (Refatorar)**
   - Melhorar o código mantendo os testes passando
   - Eliminar duplicação
   - Melhorar legibilidade e estrutura
   - Rodar todos os testes para garantir que nada quebrou

### Tipos de Testes

#### Backend

**Testes Unitários** (`tests/unit/`)
- Testam funções/métodos isolados
- Mockam dependências externas (DB, APIs)
- Rápidos e específicos
- Framework: `pytest`
- Exemplo: testar `CoinService.credit_coins()` mockando DB

**Testes de Integração** (`tests/integration/`)
- Testam interação entre componentes
- Usam banco de dados de teste
- Testam endpoints completos (request → response)
- Framework: `pytest` + `Flask test client`
- Exemplo: testar `POST /coins/admin/credit` salvando no DB

**Testes E2E** (`tests/e2e/`)
- Testam fluxo completo do usuário
- Usam banco de dados de teste ou mocks
- Simulam cenários reais
- Framework: `pytest` + `Selenium` (opcional)
- Exemplo: criar competição → inscrever aluno → entregar prova → verificar moedas

#### Frontend

**Testes Unitários** (`src/__tests__/unit/`)
- Testam componentes isolados
- Mockam props e contextos
- Framework: `Jest` + `React Testing Library`
- Exemplo: testar `CoinBalance` component

**Testes de Integração** (`src/__tests__/integration/`)
- Testam fluxos entre componentes
- Mockam chamadas de API
- Framework: `Jest` + `React Testing Library` + `MSW` (Mock Service Worker)
- Exemplo: testar fluxo de inscrição (lista → modal → confirmação)

**Testes E2E** (`e2e/`)
- Testam aplicação completa
- Usam navegador real
- Framework: `Cypress` ou `Playwright`
- Exemplo: aluno se inscreve, faz prova e vê moedas ganhas

### Setup de Testes

#### Backend

```python
# tests/conftest.py
import pytest
from app import create_app, db

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def student_fixture(app):
    # Cria aluno de teste
    student = Student(nome="Test Student", ...)
    db.session.add(student)
    db.session.commit()
    return student
```

#### Frontend

```javascript
// src/setupTests.js
import '@testing-library/jest-dom';
import { server } from './mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Cobertura de Testes

**Mínimo aceitável**:
- Backend: 80% de cobertura (models, services, routes)
- Frontend: 70% de cobertura (componentes, páginas)

**Comando**:
```bash
# Backend
pytest --cov=app --cov-report=html

# Frontend
npm test -- --coverage
```

---

## Etapa 1: Sistema de Moedas (base)

### Objetivo
Criar a infraestrutura básica de moedas: saldo, transações e histórico. Esta é a fundação para todo o sistema de recompensas.

### Backend

#### 1.1 Migrations
**Arquivo**: `migrations/versions/add_student_coins_system.py`

```python
# Tabela: student_coins
- id (String/UUID, PK)
- student_id (String, FK → student.id, UNIQUE)
- balance (Integer, default=0)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

# Tabela: coin_transactions
- id (String/UUID, PK)
- student_id (String, FK → student.id)
- amount (Integer) # positivo = crédito, negativo = débito
- balance_before (Integer) # saldo antes da transação
- balance_after (Integer) # saldo depois da transação
- reason (String) # competition_participation, competition_rank_1, etc.
- competition_id (String, FK → competitions.id, nullable)
- test_session_id (String, FK → test_sessions.id, nullable)
- description (Text, nullable) # descrição adicional
- created_at (TIMESTAMP)
```

#### 1.2 Models
**Arquivos**:
- `app/models/studentCoins.py`
- `app/models/coinTransaction.py`

```python
# StudentCoins
- Relacionamento com Student
- Método: credit(amount, reason, **kwargs) # adiciona moedas
- Método: debit(amount, reason, **kwargs) # remove moedas (futuro: loja)
- Método: get_balance() # retorna saldo atual

# CoinTransaction
- Relacionamento com Student, Competition (opcional), TestSession (opcional)
- Criar automaticamente ao creditar/debitar
```

#### 1.3 Routes
**Arquivo**: `app/routes/coin_routes.py`

```python
# GET /coins/balance
# Retorna saldo do aluno logado
# Permissões: aluno (próprio saldo), professor/admin (qualquer aluno)

# GET /coins/transactions
# Lista histórico de transações do aluno
# Query params: ?student_id=xxx (admin), ?limit=50, ?offset=0
# Permissões: aluno (próprio histórico), professor/admin (qualquer aluno)

# GET /coins/transactions/:id
# Detalhes de uma transação específica
# Permissões: aluno (própria transação), professor/admin (qualquer transação)

# POST /coins/admin/credit (admin apenas)
# Creditar moedas manualmente (bônus, eventos, etc.)
# Body: { student_id, amount, reason, description }
```

#### 1.4 Services
**Arquivo**: `app/services/coin_service.py`

```python
class CoinService:
    @staticmethod
    def get_balance(student_id):
        # Retorna saldo do aluno (ou 0 se não existir registro)
    
    @staticmethod
    def credit_coins(student_id, amount, reason, **kwargs):
        # Credita moedas, cria/atualiza student_coins, registra em coin_transactions
        # Retorna: transaction criada
    
    @staticmethod
    def debit_coins(student_id, amount, reason, **kwargs):
        # Debita moedas (verifica saldo suficiente)
        # Retorna: transaction criada ou erro
    
    @staticmethod
    def get_transaction_history(student_id, limit=50, offset=0):
        # Lista transações do aluno (paginado)
```

### Frontend

#### 1.1 Componente: CoinBalance (reutilizável)
**Arquivo**: `src/components/Coins/CoinBalance.tsx`

**Descrição**: Exibe o saldo de moedas do aluno (ícone + valor).

**Props**:
- `studentId` (opcional, padrão: aluno logado)
- `size` (small, medium, large)
- `showLabel` (boolean, mostra "Moedas" ou só o valor)

**Funcionalidades**:
- Busca saldo via API (`GET /coins/balance`)
- Atualiza em tempo real (opcional: websocket ou polling)
- Tooltip com "Ver histórico" (link para página de transações)

#### 1.2 Página: CoinHistory
**Arquivo**: `src/pages/Student/CoinHistory.tsx`

**Rota**: `/student/coins/history` ou `/coins/history`

**Descrição**: Página completa de histórico de moedas do aluno.

**Componentes**:
- **Header**: saldo atual (CoinBalance grande) + filtros
- **Filtros**: por período (última semana, mês, tudo), por tipo (participação, ranking, bônus)
- **Lista de transações**: card/tabela com:
  - Data/hora
  - Valor (+50, +100, -20)
  - Motivo (ícone + label: "Participação - Competição X", "1º Lugar - Competição Y")
  - Saldo após transação
- **Paginação**: carregar mais transações

#### 1.3 Integração no Header/Navbar
**Arquivo**: `src/components/Layout/StudentNavbar.tsx` (ou similar)

**Descrição**: Adicionar componente `<CoinBalance size="small" />` no canto superior direito do header do aluno, sempre visível.

**Funcionalidades**:
- Clique abre dropdown com:
  - Saldo atual
  - Últimas 3 transações (resumo)
  - Link "Ver histórico completo" → vai para `/coins/history`

### Testes (TDD)

#### Backend - Testes Unitários

**Arquivo**: `tests/unit/services/test_coin_service.py`

```python
# 🔴 RED: Escrever teste primeiro
def test_get_balance_returns_zero_for_new_student(student_fixture):
    """Saldo inicial deve ser 0 para aluno novo"""
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 0

def test_credit_coins_increases_balance(student_fixture):
    """Creditar moedas deve aumentar saldo"""
    CoinService.credit_coins(student_fixture.id, 50, 'test')
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 50

def test_credit_coins_creates_transaction(student_fixture):
    """Creditar moedas deve criar transação"""
    CoinService.credit_coins(student_fixture.id, 50, 'test', description='Test credit')
    
    transaction = CoinTransaction.query.filter_by(student_id=student_fixture.id).first()
    assert transaction is not None
    assert transaction.amount == 50
    assert transaction.reason == 'test'
    assert transaction.balance_after == 50

def test_debit_coins_decreases_balance(student_fixture):
    """Debitar moedas deve diminuir saldo"""
    CoinService.credit_coins(student_fixture.id, 100, 'test')
    CoinService.debit_coins(student_fixture.id, 30, 'purchase')
    
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 70

def test_debit_coins_fails_with_insufficient_balance(student_fixture):
    """Debitar mais que o saldo deve falhar"""
    CoinService.credit_coins(student_fixture.id, 10, 'test')
    
    with pytest.raises(InsufficientBalanceError):
        CoinService.debit_coins(student_fixture.id, 50, 'purchase')

def test_multiple_credits_accumulate(student_fixture):
    """Múltiplos créditos devem acumular"""
    CoinService.credit_coins(student_fixture.id, 50, 'test1')
    CoinService.credit_coins(student_fixture.id, 30, 'test2')
    CoinService.credit_coins(student_fixture.id, 20, 'test3')
    
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 100

# 🟢 GREEN: Implementar CoinService para passar nos testes
# 🔵 REFACTOR: Melhorar código mantendo testes passando
```

**Arquivo**: `tests/unit/models/test_student_coins.py`

```python
def test_student_coins_creation(student_fixture):
    """StudentCoins deve ser criado com saldo 0"""
    coins = StudentCoins(student_id=student_fixture.id)
    db.session.add(coins)
    db.session.commit()
    
    assert coins.balance == 0
    assert coins.student_id == student_fixture.id

def test_student_coins_unique_per_student(student_fixture):
    """Deve haver apenas um StudentCoins por aluno"""
    coins1 = StudentCoins(student_id=student_fixture.id)
    db.session.add(coins1)
    db.session.commit()
    
    coins2 = StudentCoins(student_id=student_fixture.id)
    db.session.add(coins2)
    
    with pytest.raises(IntegrityError):
        db.session.commit()
```

#### Backend - Testes de Integração

**Arquivo**: `tests/integration/routes/test_coin_routes.py`

```python
def test_get_balance_endpoint(client, student_fixture, auth_headers):
    """GET /coins/balance deve retornar saldo"""
    # Setup: creditar moedas
    CoinService.credit_coins(student_fixture.id, 150, 'test')
    
    # Act
    response = client.get('/coins/balance', headers=auth_headers)
    
    # Assert
    assert response.status_code == 200
    assert response.json['balance'] == 150

def test_get_transactions_endpoint(client, student_fixture, auth_headers):
    """GET /coins/transactions deve listar transações"""
    # Setup
    CoinService.credit_coins(student_fixture.id, 50, 'test1')
    CoinService.credit_coins(student_fixture.id, 30, 'test2')
    
    # Act
    response = client.get('/coins/transactions', headers=auth_headers)
    
    # Assert
    assert response.status_code == 200
    assert len(response.json['transactions']) == 2
    assert response.json['transactions'][0]['amount'] == 30  # mais recente primeiro

def test_admin_credit_coins_endpoint(client, admin_headers, student_fixture):
    """POST /coins/admin/credit deve creditar moedas (admin)"""
    # Act
    response = client.post('/coins/admin/credit', 
        json={
            'student_id': student_fixture.id,
            'amount': 100,
            'reason': 'bonus',
            'description': 'Admin bonus'
        },
        headers=admin_headers
    )
    
    # Assert
    assert response.status_code == 201
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 100

def test_student_cannot_access_admin_credit(client, student_fixture, auth_headers):
    """Aluno não pode acessar endpoint de admin"""
    response = client.post('/coins/admin/credit',
        json={'student_id': student_fixture.id, 'amount': 100, 'reason': 'hack'},
        headers=auth_headers
    )
    
    assert response.status_code == 403
```

#### Backend - Testes E2E

**Arquivo**: `tests/e2e/test_coin_flow.py`

```python
def test_complete_coin_flow(client, student_fixture, auth_headers):
    """Fluxo completo: creditar → listar → verificar histórico"""
    # 1. Verificar saldo inicial (0)
    response = client.get('/coins/balance', headers=auth_headers)
    assert response.json['balance'] == 0
    
    # 2. Creditar moedas (simulando participação em competição)
    CoinService.credit_coins(student_fixture.id, 50, 'competition_participation', 
                            competition_id='comp-123', description='Competição Matemática')
    
    # 3. Verificar saldo atualizado
    response = client.get('/coins/balance', headers=auth_headers)
    assert response.json['balance'] == 50
    
    # 4. Verificar histórico
    response = client.get('/coins/transactions', headers=auth_headers)
    transactions = response.json['transactions']
    assert len(transactions) == 1
    assert transactions[0]['amount'] == 50
    assert transactions[0]['reason'] == 'competition_participation'
    assert 'Competição Matemática' in transactions[0]['description']
```

#### Frontend - Testes Unitários

**Arquivo**: `src/components/Coins/__tests__/CoinBalance.test.tsx`

```typescript
// 🔴 RED: Escrever teste primeiro
import { render, screen, waitFor } from '@testing-library/react';
import { CoinBalance } from '../CoinBalance';
import { server } from '../../../mocks/server';
import { rest } from 'msw';

describe('CoinBalance Component', () => {
  it('should display balance correctly', async () => {
    // Mock API response
    server.use(
      rest.get('/coins/balance', (req, res, ctx) => {
        return res(ctx.json({ balance: 150 }));
      })
    );
    
    render(<CoinBalance />);
    
    // Deve mostrar loading primeiro
    expect(screen.getByText(/carregando/i)).toBeInTheDocument();
    
    // Depois deve mostrar saldo
    await waitFor(() => {
      expect(screen.getByText('150')).toBeInTheDocument();
    });
  });
  
  it('should display 0 for new student', async () => {
    server.use(
      rest.get('/coins/balance', (req, res, ctx) => {
        return res(ctx.json({ balance: 0 }));
      })
    );
    
    render(<CoinBalance />);
    
    await waitFor(() => {
      expect(screen.getByText('0')).toBeInTheDocument();
    });
  });
  
  it('should respect size prop', () => {
    render(<CoinBalance size="large" />);
    const container = screen.getByTestId('coin-balance');
    expect(container).toHaveClass('coin-balance--large');
  });
  
  // 🟢 GREEN: Implementar CoinBalance para passar nos testes
  // 🔵 REFACTOR: Melhorar código mantendo testes passando
});
```

**Arquivo**: `src/pages/Student/__tests__/CoinHistory.test.tsx`

```typescript
describe('CoinHistory Page', () => {
  it('should display transaction list', async () => {
    server.use(
      rest.get('/coins/transactions', (req, res, ctx) => {
        return res(ctx.json({
          transactions: [
            { id: '1', amount: 50, reason: 'competition_participation', created_at: '2024-01-15' },
            { id: '2', amount: 100, reason: 'competition_rank_1', created_at: '2024-01-14' },
          ]
        }));
      })
    );
    
    render(<CoinHistory />);
    
    await waitFor(() => {
      expect(screen.getByText('+50')).toBeInTheDocument();
      expect(screen.getByText('+100')).toBeInTheDocument();
    });
  });
  
  it('should filter transactions by type', async () => {
    render(<CoinHistory />);
    
    const filterSelect = screen.getByLabelText(/tipo/i);
    fireEvent.change(filterSelect, { target: { value: 'ranking' } });
    
    await waitFor(() => {
      expect(screen.queryByText('Participação')).not.toBeInTheDocument();
      expect(screen.getByText('1º Lugar')).toBeInTheDocument();
    });
  });
});
```

#### Frontend - Testes E2E

**Arquivo**: `e2e/coins/coin-flow.spec.ts` (Cypress)

```typescript
describe('Coin System Flow', () => {
  beforeEach(() => {
    cy.login('student@test.com', 'password');
  });
  
  it('should display coin balance in header', () => {
    cy.visit('/student/dashboard');
    cy.get('[data-testid="coin-balance"]').should('be.visible');
    cy.get('[data-testid="coin-balance"]').should('contain', '0'); // aluno novo
  });
  
  it('should navigate to coin history page', () => {
    cy.visit('/student/dashboard');
    cy.get('[data-testid="coin-balance"]').click();
    cy.contains('Ver histórico completo').click();
    
    cy.url().should('include', '/coins/history');
    cy.contains('Histórico de Moedas').should('be.visible');
  });
  
  it('should display updated balance after earning coins', () => {
    // Simular ganho de moedas (via backend ou mock)
    cy.request('POST', '/api/coins/admin/credit', {
      student_id: Cypress.env('studentId'),
      amount: 50,
      reason: 'test'
    });
    
    cy.visit('/student/dashboard');
    cy.get('[data-testid="coin-balance"]').should('contain', '50');
  });
});
```

### Checklist TDD - Etapa 1

#### Backend
- [ ] 🔴 Escrever testes unitários de `CoinService`
- [ ] 🟢 Implementar `CoinService` (todos os testes passando)
- [ ] 🔵 Refatorar `CoinService`
- [ ] 🔴 Escrever testes de models (`StudentCoins`, `CoinTransaction`)
- [ ] 🟢 Implementar models
- [ ] 🔵 Refatorar models
- [ ] 🔴 Escrever testes de integração das routes
- [ ] 🟢 Implementar routes
- [ ] 🔵 Refatorar routes
- [ ] 🔴 Escrever testes E2E do fluxo completo
- [ ] 🟢 Garantir fluxo E2E funcionando
- [ ] ✅ Cobertura: mínimo 80%

#### Frontend
- [ ] 🔴 Escrever testes de `CoinBalance` component
- [ ] 🟢 Implementar `CoinBalance`
- [ ] 🔵 Refatorar `CoinBalance`
- [ ] 🔴 Escrever testes de `CoinHistory` page
- [ ] 🟢 Implementar `CoinHistory`
- [ ] 🔵 Refatorar `CoinHistory`
- [ ] 🔴 Escrever testes E2E (Cypress)
- [ ] 🟢 Garantir fluxo E2E funcionando
- [ ] ✅ Cobertura: mínimo 70%

---

## Etapa 2: Competições CRUD (estrutura básica)

### Objetivo
Criar a estrutura de competições: tabelas, modelos, endpoints CRUD e página de gerenciamento (admin/coordenador). Ainda sem inscrição de aluno ou aplicação de prova.

### Backend

#### 2.1 Migrations
**Arquivo**: `migrations/versions/add_competitions_table.py`

```python
# Tabela: competitions
- id (String/UUID, PK)
- name (String, required)
- description (Text)
- test_id (String, FK → test.id, nullable inicialmente)
- subject_id (String, FK → subject.id)
- level (Integer) # 1, 2, 3...
- scope (String, default='individual') # individual, turma, escola, municipio
- scope_filter (JSON, nullable) # {"class_ids": [...], "school_ids": [...]}
- enrollment_start (TIMESTAMP)
- enrollment_end (TIMESTAMP)
- application (TIMESTAMP)
- expiration (TIMESTAMP)
- timezone (String, default='America/Sao_Paulo')
- question_mode (String, default='auto_random') # auto_random, manual
- question_rules (JSON, nullable) # regras para sorteio
- reward_config (JSON, required) # {"participation_coins": 50, "ranking_rewards": [...]}
- ranking_criteria (String, default='nota') # nota, tempo, acertos
- ranking_tiebreaker (String, default='tempo_entrega')
- ranking_visibility (String, default='final') # realtime, final
- max_participants (Integer, nullable)
- recurrence (String, default='manual') # manual, weekly, biweekly, monthly
- template_id (String, FK → competition_templates.id, nullable)
- status (String, default='rascunho') # rascunho, aberta, em_andamento, aguardando_resultado, encerrada, cancelada
- created_by (String, FK → users.id)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### 2.2 Models
**Arquivo**: `app/models/competition.py`

```python
class Competition(db.Model):
    # Campos conforme migration
    # Relacionamentos:
    - test (relationship com Test)
    - subject (relationship com Subject)
    - creator (relationship com User)
    - template (relationship com CompetitionTemplate, nullable)
    
    # Propriedades:
    @property
    def is_enrollment_open(self):
        # Verifica se está no período de inscrição
    
    @property
    def is_application_open(self):
        # Verifica se está no período de aplicação
    
    @property
    def is_finished(self):
        # Verifica se expirou
    
    @property
    def enrolled_count(self):
        # Conta quantos alunos inscritos (via student_test_olimpics)
    
    @property
    def available_slots(self):
        # Vagas disponíveis (max_participants - enrolled_count)
```

#### 2.3 Routes
**Arquivo**: `app/routes/competition_routes.py`

```python
# POST /competitions/
# Cria competição (admin/coordenador)
# Body: todos os campos (name, description, level, scope, datas, reward_config, etc.)
# Se question_mode = 'auto_random': usar question_rules para sortear questões e criar Test + test_questions
# Se question_mode = 'manual': esperar seleção de questões (POST /competitions/:id/questions)
# Retorna: competition criada

# GET /competitions/
# Lista todas competições (admin/coordenador)
# Query params: ?status=aberta, ?level=1, ?subject_id=xxx, ?scope=individual
# Retorna: lista de competitions

# GET /competitions/:id
# Detalhes de uma competição
# Retorna: competition com test, subject, creator, enrolled_count, etc.

# PATCH /competitions/:id
# Atualiza competição (admin/coordenador)
# Regras: só pode editar se status = 'rascunho' ou 'aberta' E enrollment_start no futuro
# Body: campos editáveis (name, description, datas, reward_config, etc.)

# DELETE /competitions/:id
# Deleta competição (admin/coordenador)
# Regras: só pode deletar se status = 'rascunho' e não tem inscritos
# Alternativa: cancelar (PATCH status → 'cancelada')

# POST /competitions/:id/questions (se question_mode = 'manual')
# Adiciona questões manualmente à competição
# Body: { question_ids: [...] }
# Cria Test + test_questions com as questões selecionadas

# POST /competitions/:id/publish
# Publica competição (muda status de 'rascunho' → 'aberta')
# Valida: test_id existe, datas válidas, reward_config válido

# PATCH /competitions/:id/cancel
# Cancela competição (muda status → 'cancelada')
```

#### 2.4 Services
**Arquivo**: `app/services/competition_service.py`

```python
class CompetitionService:
    @staticmethod
    def create_competition(data, created_by_user_id):
        # Cria competition
        # Se question_mode = 'auto_random': chama _create_test_with_random_questions()
        # Se question_mode = 'manual': deixa test_id = None (adicionar depois)
        # Retorna: competition criada
    
    @staticmethod
    def _create_test_with_random_questions(competition):
        # Sorteia questões baseado em question_rules
        # Cria Test e test_questions
        # Atualiza competition.test_id
    
    @staticmethod
    def add_questions_manually(competition_id, question_ids):
        # Cria Test e test_questions com as questões fornecidas
        # Atualiza competition.test_id
    
    @staticmethod
    def publish_competition(competition_id):
        # Valida e muda status para 'aberta'
    
    @staticmethod
    def cancel_competition(competition_id, reason=None):
        # Cancela competição, notifica inscritos (se houver)
    
    @staticmethod
    def get_available_competitions_for_student(student_id):
        # Filtra competições disponíveis para o aluno
        # (nível, escopo, período de inscrição, vagas disponíveis)
        # Usado na Etapa 3
```

### Frontend

#### 2.1 Página: CompetitionList (Admin)
**Arquivo**: `src/pages/Admin/Competitions/CompetitionList.tsx`

**Rota**: `/admin/competitions` ou `/coordenador/competitions`

**Descrição**: Lista todas as competições criadas (admin/coordenador).

**Componentes**:
- **Header**: "Competições" + botão "Nova Competição" → modal/página de criação
- **Filtros**: por status (todas, rascunho, abertas, encerradas), por disciplina, por nível
- **Tabela/Cards**: cada competição mostra:
  - Nome
  - Disciplina | Nível
  - Status (badge colorido)
  - Período (inscrição + aplicação)
  - Inscritos / Vagas (ex: 45/100 ou 45/∞)
  - Ações: Ver, Editar, Cancelar/Excluir
- **Paginação**

#### 2.2 Modal/Página: CreateCompetitionModal
**Arquivo**: `src/pages/Admin/Competitions/CreateCompetitionModal.tsx`

**Descrição**: Modal/página de criação de competição (pode ser multi-etapas).

**Etapas do formulário**:

**Etapa 1: Informações básicas**
- Nome (input text)
- Descrição (textarea, opcional)
- Disciplina (select)
- Nível (select: 1, 2, 3... ou labels: Anos Iniciais, Anos Finais, etc.)
- Escopo (select: Individual, Turma, Escola, Município)
  - Se Turma: multi-select de turmas
  - Se Escola: multi-select de escolas
  - Se Município: multi-select de municípios

**Etapa 2: Datas**
- Período de inscrição (date range: início + fim)
- Período de aplicação (date range: início + fim)
- Timezone (select, padrão: America/Sao_Paulo)
- Validação: application >= enrollment_end

**Etapa 3: Questões**
- Modo de questões (radio):
  - [ ] Sorteio automático
    - Quantidade de questões (number input)
    - Dificuldade (select: todas, fácil, média, difícil, ou multi-select)
    - Tópicos/skills (opcional, multi-select)
  - [ ] Seleção manual
    - Botão "Selecionar questões" → abre modal de seleção (lista questões do banco filtradas por disciplina/nível)

**Etapa 4: Recompensas**
- Moedas por participação (number input, ex: 50)
- Ranking:
  - Botão "Adicionar posição premiada"
  - Lista de posições: Posição (1, 2, 3...) + Moedas (input)
  - Exemplo visual: 1º → 100 moedas, 2º → 50 moedas, 3º → 25 moedas

**Etapa 5: Configurações avançadas**
- Critério de ranking (select: Nota, Tempo, Acertos, Pontuação ponderada)
- Visibilidade do ranking (select: Tempo real, Só no final)
- Limite de participantes (number input, deixar vazio = ilimitado)
- Recorrência (select: Manual, Semanal, Quinzenal, Mensal) - apenas informativo nesta etapa (templates na Etapa 6)

**Botões finais**:
- "Salvar como rascunho" (cria com status='rascunho')
- "Criar e publicar" (cria com status='aberta')

#### 2.3 Página: CompetitionDetails (Admin)
**Arquivo**: `src/pages/Admin/Competitions/CompetitionDetails.tsx`

**Rota**: `/admin/competitions/:id`

**Descrição**: Detalhes completos da competição (admin/coordenador).

**Componentes**:
- **Header**: Nome da competição + status (badge) + botões (Editar, Cancelar, Excluir)
- **Seção: Informações**:
  - Disciplina, Nível, Escopo
  - Datas (inscrição, aplicação)
  - Questões (quantidade, modo)
  - Recompensas (participação + ranking)
- **Seção: Inscritos** (lista de alunos inscritos, se houver):
  - Nome, Turma, Data de inscrição
  - Botão "Ver detalhes do aluno"
- **Seção: Resultados** (se competição encerrada):
  - Ranking final
  - Quem ganhou moedas e quanto
- **Botões de ação**:
  - "Editar competição" (se status = rascunho ou aberta)
  - "Publicar" (se status = rascunho)
  - "Cancelar competição" (confirmar em modal)

#### 2.4 Modal: EditCompetitionModal
**Arquivo**: `src/pages/Admin/Competitions/EditCompetitionModal.tsx`

**Descrição**: Similar a CreateCompetitionModal, mas com campos preenchidos.

**Regras**:
- Se status != 'rascunho': desabilita campos críticos (questões, datas passadas)
- Só permite editar descrição, recompensas (se não houver inscritos) e status

### Testes (TDD) - Etapa 2

#### Backend - Testes Unitários

**Arquivo**: `tests/unit/services/test_competition_service.py`

```python
def test_create_competition_with_auto_random_questions(subject_fixture, admin_user):
    """Criar competição com sorteio automático deve criar test e questões"""
    # 🔴 RED
    data = {
        'name': 'Competição Teste',
        'subject_id': subject_fixture.id,
        'level': 1,
        'question_mode': 'auto_random',
        'question_rules': {'num_questions': 10, 'difficulty_level': 'media'},
        'reward_config': {'participation_coins': 50, 'ranking_rewards': []},
        # ... outras configurações
    }
    
    competition = CompetitionService.create_competition(data, admin_user.id)
    
    assert competition.test_id is not None
    assert len(competition.test.questions) == 10
    # 🟢 GREEN: implementar
    # 🔵 REFACTOR: melhorar

def test_create_competition_manual_questions_leaves_test_null(admin_user):
    """Competição manual não cria test automaticamente"""
    data = {
        'name': 'Competição Manual',
        'question_mode': 'manual',
        # ... outras configurações
    }
    
    competition = CompetitionService.create_competition(data, admin_user.id)
    assert competition.test_id is None

def test_publish_competition_validates_test_exists():
    """Publicar competição deve validar que test existe"""
    competition = Competition(name='Test', question_mode='manual', test_id=None)
    db.session.add(competition)
    db.session.commit()
    
    with pytest.raises(ValidationError, match='Test não criado'):
        CompetitionService.publish_competition(competition.id)

def test_publish_competition_validates_dates():
    """Publicar competição deve validar datas"""
    competition = Competition(
        enrollment_start=datetime(2024, 1, 10),
        enrollment_end=datetime(2024, 1, 5),  # antes do início
        # ...
    )
    
    with pytest.raises(ValidationError, match='datas inválidas'):
        CompetitionService.publish_competition(competition.id)
```

**Arquivo**: `tests/unit/models/test_competition.py`

```python
def test_competition_is_enrollment_open_property():
    """Propriedade is_enrollment_open deve retornar corretamente"""
    now = datetime.utcnow()
    competition = Competition(
        enrollment_start=now - timedelta(hours=1),
        enrollment_end=now + timedelta(hours=1)
    )
    
    assert competition.is_enrollment_open is True

def test_competition_enrolled_count_property(student_fixture, competition_fixture):
    """Propriedade enrolled_count deve contar inscritos"""
    # Inscrever 3 alunos
    for i in range(3):
        StudentTestOlimpics(
            student_id=f'student-{i}',
            test_id=competition_fixture.test_id
        ).save()
    
    assert competition_fixture.enrolled_count == 3

def test_competition_available_slots_with_limit():
    """available_slots deve calcular vagas disponíveis"""
    competition = Competition(max_participants=10)
    # Simular 7 inscritos
    competition.enrolled_count = 7  # mock
    
    assert competition.available_slots == 3
```

#### Backend - Testes de Integração

**Arquivo**: `tests/integration/routes/test_competition_routes.py`

```python
def test_create_competition_endpoint(client, admin_headers, subject_fixture):
    """POST /competitions/ deve criar competição"""
    response = client.post('/competitions/',
        json={
            'name': 'Competição Teste API',
            'subject_id': subject_fixture.id,
            'level': 1,
            'enrollment_start': '2024-06-01T00:00:00',
            'enrollment_end': '2024-06-03T23:59:59',
            'application': '2024-06-04T00:00:00',
            'expiration': '2024-06-07T23:59:59',
            'question_mode': 'auto_random',
            'question_rules': {'num_questions': 5},
            'reward_config': {'participation_coins': 50, 'ranking_rewards': []}
        },
        headers=admin_headers
    )
    
    assert response.status_code == 201
    assert 'id' in response.json
    
    # Verificar no banco
    competition = Competition.query.get(response.json['id'])
    assert competition.name == 'Competição Teste API'

def test_list_competitions_endpoint(client, admin_headers):
    """GET /competitions/ deve listar competições"""
    # Criar 3 competições
    for i in range(3):
        Competition(name=f'Comp {i}', status='aberta').save()
    
    response = client.get('/competitions/', headers=admin_headers)
    
    assert response.status_code == 200
    assert len(response.json['competitions']) >= 3

def test_publish_competition_endpoint(client, admin_headers, competition_fixture):
    """POST /competitions/:id/publish deve publicar"""
    response = client.post(f'/competitions/{competition_fixture.id}/publish',
        headers=admin_headers
    )
    
    assert response.status_code == 200
    
    competition = Competition.query.get(competition_fixture.id)
    assert competition.status == 'aberta'

def test_student_cannot_create_competition(client, student_headers):
    """Aluno não pode criar competição"""
    response = client.post('/competitions/',
        json={'name': 'Tentativa Hack'},
        headers=student_headers
    )
    
    assert response.status_code == 403
```

#### Frontend - Testes Unitários

**Arquivo**: `src/pages/Admin/Competitions/__tests__/CreateCompetitionModal.test.tsx`

```typescript
describe('CreateCompetitionModal', () => {
  it('should render all form steps', () => {
    render(<CreateCompetitionModal open={true} onClose={jest.fn()} />);
    
    expect(screen.getByText('Informações básicas')).toBeInTheDocument();
    expect(screen.getByText('Datas')).toBeInTheDocument();
    expect(screen.getByText('Questões')).toBeInTheDocument();
  });
  
  it('should validate required fields', async () => {
    render(<CreateCompetitionModal open={true} onClose={jest.fn()} />);
    
    const submitButton = screen.getByText('Criar competição');
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText('Nome é obrigatório')).toBeInTheDocument();
      expect(screen.getByText('Disciplina é obrigatória')).toBeInTheDocument();
    });
  });
  
  it('should validate dates (application >= enrollment_end)', async () => {
    render(<CreateCompetitionModal open={true} onClose={jest.fn()} />);
    
    // Preencher datas inválidas
    fireEvent.change(screen.getByLabelText('Fim da inscrição'), {
      target: { value: '2024-06-10' }
    });
    fireEvent.change(screen.getByLabelText('Início da aplicação'), {
      target: { value: '2024-06-05' }  // antes do fim da inscrição
    });
    
    fireEvent.click(screen.getByText('Próximo'));
    
    await waitFor(() => {
      expect(screen.getByText(/data de aplicação deve ser após/i)).toBeInTheDocument();
    });
  });
  
  it('should submit form with correct data', async () => {
    const onSuccess = jest.fn();
    render(<CreateCompetitionModal open={true} onClose={jest.fn()} onSuccess={onSuccess} />);
    
    // Preencher todos os campos...
    // ... (formulário completo)
    
    fireEvent.click(screen.getByText('Criar competição'));
    
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
```

### Checklist TDD - Etapa 2

#### Backend
- [ ] 🔴 Escrever testes unitários de `CompetitionService`
- [ ] 🟢 Implementar `CompetitionService`
- [ ] 🔵 Refatorar `CompetitionService`
- [ ] 🔴 Escrever testes de model `Competition`
- [ ] 🟢 Implementar `Competition` model
- [ ] 🔵 Refatorar model
- [ ] 🔴 Escrever testes de integração das routes
- [ ] 🟢 Implementar routes CRUD
- [ ] 🔵 Refatorar routes
- [ ] ✅ Cobertura: mínimo 80%

#### Frontend
- [ ] 🔴 Escrever testes de `CreateCompetitionModal`
- [ ] 🟢 Implementar modal com validações
- [ ] 🔵 Refatorar modal
- [ ] 🔴 Escrever testes de `CompetitionList`
- [ ] 🟢 Implementar lista
- [ ] 🔵 Refatorar lista
- [ ] 🔴 Escrever testes E2E (Cypress)
- [ ] 🟢 Garantir fluxo E2E funcionando
- [ ] ✅ Cobertura: mínimo 70%

---

## Etapa 3: Inscrição e Listagem (Aluno)

### Objetivo
Permitir que alunos vejam competições disponíveis e se inscrevam. Integrar com `student_test_olimpics` para liberar a prova.

### Backend

#### 3.1 Routes (adicionar em `competition_routes.py`)

```python
# GET /competitions/available
# Lista competições disponíveis para o aluno logado
# Filtros automáticos: nível do aluno, escopo (turma/escola/município), período de inscrição, vagas disponíveis
# Query params: ?subject_id=xxx (filtrar por disciplina)
# Permissões: aluno (próprias competições), professor/admin (qualquer aluno via ?student_id=xxx)
# Retorna: lista de competitions disponíveis

# GET /competitions/:id/details
# Detalhes de uma competição para o aluno
# Inclui: se já está inscrito, quantas vagas restantes, ranking (se visível)
# Permissões: aluno (se competição disponível para ele), professor/admin
# Retorna: competition + is_enrolled, available_slots

# POST /competitions/:id/enroll
# Inscreve o aluno na competição
# Validações:
#   - Competição no período de inscrição
#   - Aluno pertence ao nível/escopo
#   - Vagas disponíveis (se houver limite)
#   - Aluno não inscrito ainda
# Ação: cria registro em student_test_olimpics (student_id, test_id, application, expiration)
# Retorna: sucesso ou erro

# DELETE /competitions/:id/unenroll
# Remove inscrição do aluno (se permitido: antes do período de aplicação)
# Ação: remove registro de student_test_olimpics
# Retorna: sucesso ou erro
```

#### 3.2 Services (adicionar em `competition_service.py`)

```python
@staticmethod
def get_available_competitions_for_student(student_id):
    # Busca aluno (série, turma, escola, município)
    # Filtra competições:
    #   - status = 'aberta'
    #   - enrollment_start <= now <= enrollment_end
    #   - nível compatível com série do aluno
    #   - escopo:
    #       - individual: ok
    #       - turma: class_id do aluno em scope_filter.class_ids
    #       - escola: school_id do aluno em scope_filter.school_ids
    #       - municipio: municipality_id do aluno em scope_filter.municipality_ids
    #   - vagas disponíveis (se max_participants)
    # Retorna: lista de competitions

@staticmethod
def enroll_student(competition_id, student_id):
    # Valida tudo (acima)
    # Cria StudentTestOlimpics:
    #   - student_id
    #   - test_id = competition.test_id
    #   - application = competition.application
    #   - expiration = competition.expiration
    #   - timezone = competition.timezone
    # Retorna: sucesso ou erro

@staticmethod
def unenroll_student(competition_id, student_id):
    # Valida: antes do período de aplicação
    # Remove StudentTestOlimpics
    # Retorna: sucesso
```

### Frontend

#### 3.1 Página: CompetitionListStudent
**Arquivo**: `src/pages/Student/Competitions/CompetitionListStudent.tsx`

**Rota**: `/student/competitions` ou `/competitions` (para aluno)

**Descrição**: Lista de competições disponíveis para o aluno se inscrever.

**Componentes**:
- **Header**: "Competições Disponíveis" + filtro por disciplina
- **Abas (tabs)**:
  - "Abertas" (pode se inscrever agora)
  - "Próximas" (inscrição abre em breve)
  - "Minhas Inscrições" (competições em que já está inscrito)
  - "Encerradas" (já participou ou perdeu prazo)
- **Cards de competição**:
  - Nome da competição
  - Disciplina | Nível
  - Período de inscrição (ícone + data)
  - Período de aplicação (ícone + data)
  - Vagas: "45/100" ou "∞" (ilimitado)
  - Recompensas: "50 moedas + prêmios para top 3" (ícone de moeda)
  - Status de inscrição:
    - Não inscrito: botão "Inscrever-se"
    - Inscrito: badge "Inscrito" + botão "Cancelar inscrição" (se permitido)
    - Vagas esgotadas: badge "Esgotado"
  - Botão "Ver detalhes" → vai para CompetitionDetailsStudent

#### 3.2 Página: CompetitionDetailsStudent
**Arquivo**: `src/pages/Student/Competitions/CompetitionDetailsStudent.tsx`

**Rota**: `/student/competitions/:id` ou `/competitions/:id`

**Descrição**: Detalhes completos de uma competição para o aluno.

**Componentes**:
- **Header**: Nome da competição + badge de status de inscrição
- **Seção: Sobre a competição**:
  - Descrição
  - Disciplina e nível
  - Quantidade de questões
  - Duração da prova (se houver)
- **Seção: Cronograma**:
  - Timeline visual:
    - Inscrição: DD/MM às HH:MM - DD/MM às HH:MM
    - Aplicação: DD/MM às HH:MM - DD/MM às HH:MM
  - Destaque no período atual (em inscrição / em aplicação)
- **Seção: Recompensas**:
  - "Ganhe 50 moedas só por participar!"
  - "Prêmios para o top 3: 1º → 100 moedas, 2º → 50 moedas, 3º → 25 moedas"
  - (visual atraente com ícones de moeda e medalhas)
- **Seção: Vagas**:
  - "45 de 100 vagas preenchidas" (barra de progresso)
  - ou "Vagas ilimitadas"
- **Seção: Ranking** (se visível):
  - Se ranking_visibility = 'realtime' E período de aplicação:
    - Exibe ranking ao vivo (atualizável)
  - Se ranking_visibility = 'final' E competição encerrada:
    - Exibe ranking final
  - Se não visível ainda: "Ranking será divulgado após o término"
- **Ações**:
  - Botão grande "Inscrever-se" (se não inscrito e no período)
  - Botão "Cancelar inscrição" (se inscrito e antes da aplicação)
  - Botão "Fazer prova" (se inscrito e no período de aplicação) → vai para a prova

#### 3.3 Modal: EnrollConfirmationModal
**Arquivo**: `src/pages/Student/Competitions/EnrollConfirmationModal.tsx`

**Descrição**: Modal de confirmação de inscrição.

**Conteúdo**:
- "Deseja se inscrever na competição [Nome]?"
- Resumo: disciplina, datas, recompensas
- Botões: "Confirmar inscrição" (chama API) e "Cancelar"

**Após confirmação**:
- Toast de sucesso: "Inscrição realizada! Boa sorte!"
- Atualiza lista (competição vai para aba "Minhas Inscrições")

#### 3.4 Integração no Header/Menu
**Arquivo**: `src/components/Layout/StudentNavbar.tsx`

**Descrição**: Adicionar item no menu "Competições" com badge mostrando quantas competições abertas há (número vermelho).

### Testes (TDD) - Etapa 3

#### Backend - Testes Principais

**Arquivo**: `tests/unit/services/test_competition_service.py` (adicionar)

```python
def test_get_available_competitions_filters_by_level(student_fixture, competition_fixture):
    """Deve filtrar competições por nível do aluno"""
    # Aluno série 5 (nível 1)
    student_fixture.grade_level = 5
    
    # Competição nível 1
    comp1 = Competition(name='Comp Nível 1', level=1, status='aberta')
    # Competição nível 2
    comp2 = Competition(name='Comp Nível 2', level=2, status='aberta')
    
    available = CompetitionService.get_available_competitions_for_student(student_fixture.id)
    
    assert comp1 in available
    assert comp2 not in available

def test_enroll_student_creates_student_test_olimpics(student_fixture, competition_fixture):
    """Inscrever aluno deve criar registro em student_test_olimpics"""
    CompetitionService.enroll_student(competition_fixture.id, student_fixture.id)
    
    record = StudentTestOlimpics.query.filter_by(
        student_id=student_fixture.id,
        test_id=competition_fixture.test_id
    ).first()
    
    assert record is not None
    assert record.application == competition_fixture.application

def test_enroll_student_fails_if_no_slots_available(student_fixture, competition_fixture):
    """Não deve inscrever se vagas esgotadas"""
    competition_fixture.max_participants = 1
    # Inscrever outro aluno
    CompetitionService.enroll_student(competition_fixture.id, 'other-student-id')
    
    with pytest.raises(NoSlotsAvailableError):
        CompetitionService.enroll_student(competition_fixture.id, student_fixture.id)

def test_unenroll_student_removes_record(student_fixture, competition_fixture):
    """Cancelar inscrição deve remover registro"""
    CompetitionService.enroll_student(competition_fixture.id, student_fixture.id)
    CompetitionService.unenroll_student(competition_fixture.id, student_fixture.id)
    
    record = StudentTestOlimpics.query.filter_by(
        student_id=student_fixture.id,
        test_id=competition_fixture.test_id
    ).first()
    
    assert record is None
```

**Arquivo**: `tests/integration/routes/test_competition_routes.py` (adicionar)

```python
def test_enroll_endpoint(client, student_fixture, student_headers, competition_fixture):
    """POST /competitions/:id/enroll deve inscrever aluno"""
    response = client.post(f'/competitions/{competition_fixture.id}/enroll',
        headers=student_headers
    )
    
    assert response.status_code == 201
    assert response.json['message'] == 'Inscrição realizada com sucesso'

def test_available_competitions_endpoint(client, student_headers):
    """GET /competitions/available deve retornar competições filtradas"""
    response = client.get('/competitions/available', headers=student_headers)
    
    assert response.status_code == 200
    assert 'competitions' in response.json
```

#### Frontend - Testes Principais

**Arquivo**: `src/pages/Student/Competitions/__tests__/CompetitionListStudent.test.tsx`

```typescript
describe('CompetitionListStudent', () => {
  it('should display available competitions', async () => {
    server.use(
      rest.get('/competitions/available', (req, res, ctx) => {
        return res(ctx.json({
          competitions: [
            { id: '1', name: 'Comp Matemática', available_slots: 50 }
          ]
        }));
      })
    );
    
    render(<CompetitionListStudent />);
    
    await waitFor(() => {
      expect(screen.getByText('Comp Matemática')).toBeInTheDocument();
    });
  });
  
  it('should enroll student on button click', async () => {
    render(<CompetitionListStudent />);
    
    const enrollButton = screen.getByText('Inscrever-se');
    fireEvent.click(enrollButton);
    
    // Confirmar modal
    const confirmButton = screen.getByText('Confirmar inscrição');
    fireEvent.click(confirmButton);
    
    await waitFor(() => {
      expect(screen.getByText('Inscrição realizada!')).toBeInTheDocument();
    });
  });
});
```

### Checklist TDD - Etapa 3

- [ ] 🔴 Testes de filtro de competições disponíveis
- [ ] 🟢 Implementar filtros (nível, escopo, vagas)
- [ ] 🔴 Testes de inscrição
- [ ] 🟢 Implementar inscrição
- [ ] 🔴 Testes de cancelamento
- [ ] 🟢 Implementar cancelamento
- [ ] 🔴 Testes frontend (lista, modal)
- [ ] 🟢 Implementar UI
- [ ] ✅ Cobertura: backend 80%, frontend 70%

---

## Etapa 4: Aplicação e Entrega (integração com prova)

### Objetivo
Integrar competições com o fluxo de prova existente: aluno acessa prova pela competição, faz e entrega. Ao entregar, concede moedas de participação.

### Backend

#### 4.1 Migrations
**Arquivo**: `migrations/versions/add_competition_rewards.py`

```python
# Tabela: competition_rewards
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id)
- student_id (String, FK → student.id)
- participation_paid_at (TIMESTAMP, nullable)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
# Constraint: unique(competition_id, student_id)
```

#### 4.2 Services (modificar existente)
**Arquivo**: `app/routes/student_answer_routes.py` (ou onde finaliza prova)

**Adicionar no fluxo de finalização de prova**:

```python
# Após finalizar TestSession (status = 'finalizada'):

# 1. Verificar se a prova é de uma competição
competition = Competition.query.filter_by(test_id=session.test_id).first()

if competition:
    # 2. Verificar se já pagou participação
    reward = CompetitionReward.query.filter_by(
        competition_id=competition.id,
        student_id=student_id
    ).first()
    
    if not reward or reward.participation_paid_at is None:
        # 3. Ler configuração de recompensa
        participation_coins = competition.reward_config.get('participation_coins', 0)
        
        if participation_coins > 0:
            # 4. Creditar moedas
            CoinService.credit_coins(
                student_id=student_id,
                amount=participation_coins,
                reason='competition_participation',
                competition_id=competition.id,
                test_session_id=session.id,
                description=f"Participação na competição: {competition.name}"
            )
            
            # 5. Marcar como pago
            if not reward:
                reward = CompetitionReward(
                    competition_id=competition.id,
                    student_id=student_id
                )
                db.session.add(reward)
            reward.participation_paid_at = datetime.utcnow()
            db.session.commit()
            
            # 6. Retornar info para frontend (toast de moedas ganhas)
            return {"coins_earned": participation_coins}
```

#### 4.3 Routes (adicionar em `competition_routes.py`)

```python
# GET /competitions/:id/my-session
# Busca sessão de prova do aluno naquela competição
# Retorna: test_session (se iniciada) ou None
# Usado para saber se aluno já iniciou/finalizou a prova

# POST /competitions/:id/start
# Inicia prova da competição (cria test_session)
# Valida:
#   - Aluno inscrito
#   - Período de aplicação
#   - Não tem sessão finalizada
# Retorna: test_session criada ou existente
```

### Frontend

#### 4.1 Modificar: CompetitionDetailsStudent
**Arquivo**: `src/pages/Student/Competitions/CompetitionDetailsStudent.tsx`

**Adicionar lógica de "Fazer prova"**:

```tsx
// Verificar status da prova:
// - Não iniciada: botão "Iniciar prova"
// - Em andamento: botão "Continuar prova" + tempo decorrido
// - Finalizada: badge "Prova concluída" + botão "Ver resultado"

// Botão "Iniciar prova":
// - Chama POST /competitions/:id/start
// - Redireciona para /test/:test_id (ou /competition/:id/test)
```

#### 4.2 Página: CompetitionTest (opcional, pode reutilizar página de prova existente)
**Arquivo**: `src/pages/Student/Competitions/CompetitionTest.tsx`

**Rota**: `/competitions/:id/test` (ou redirecionar para `/test/:test_id`)

**Descrição**: Tela de prova (reutilizar componente existente de prova).

**Diferenças**:
- Header mostra nome da competição (em vez de só "Avaliação")
- Ao finalizar: exibe modal especial de "Prova entregue na competição" com:
  - Mensagem de sucesso
  - **Moedas ganhas**: "+50 moedas!" (animação)
  - "Ranking será atualizado em breve"
  - Botão "Ver ranking" ou "Voltar para competições"

#### 4.3 Modal: CompetitionSubmitSuccessModal
**Arquivo**: `src/pages/Student/Competitions/CompetitionSubmitSuccessModal.tsx`

**Descrição**: Modal exibido após entregar prova de competição.

**Conteúdo**:
- Ícone de sucesso (check verde)
- "Prova entregue com sucesso!"
- **Destaque visual**: "+50 moedas!" (ícone de moeda animado, número pulsando)
- "Você ganhou [X] moedas por participar!"
- "Fique de olho no ranking! Primeiros colocados ganham moedas extras."
- Botões:
  - "Ver ranking" (se ranking_visibility = 'realtime')
  - "Voltar para competições"

### Testes (TDD) - Etapa 4

#### Backend - Testes Principais

**Arquivo**: `tests/integration/test_competition_participation_flow.py`

```python
def test_finalize_test_session_credits_participation_coins(client, student_fixture, competition_fixture):
    """Entregar prova de competição deve creditar moedas de participação"""
    # Setup: inscrever aluno
    CompetitionService.enroll_student(competition_fixture.id, student_fixture.id)
    
    # Criar sessão de prova
    session = TestSession(student_id=student_fixture.id, test_id=competition_fixture.test_id)
    db.session.add(session)
    db.session.commit()
    
    # Act: finalizar prova
    response = client.post(f'/test-sessions/{session.id}/finalize', headers=student_headers)
    
    # Assert: moedas creditadas
    assert response.status_code == 200
    assert response.json['coins_earned'] == 50  # participation_coins do reward_config
    
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 50

def test_participation_coins_credited_only_once(student_fixture, competition_fixture):
    """Moedas de participação só devem ser creditadas uma vez"""
    CompetitionService.enroll_student(competition_fixture.id, student_fixture.id)
    
    # Primeira entrega
    session1 = TestSession(student_id=student_fixture.id, test_id=competition_fixture.test_id)
    session1.finalize()  # credita 50 moedas
    
    # Segunda tentativa (re-fazer prova)
    session2 = TestSession(student_id=student_fixture.id, test_id=competition_fixture.test_id)
    session2.finalize()  # NÃO deve creditar novamente
    
    balance = CoinService.get_balance(student_fixture.id)
    assert balance == 50  # não 100

def test_competition_reward_records_participation_paid_at():
    """CompetitionReward deve registrar quando participação foi paga"""
    # ... após entregar prova
    
    reward = CompetitionReward.query.filter_by(
        competition_id=competition_fixture.id,
        student_id=student_fixture.id
    ).first()
    
    assert reward is not None
    assert reward.participation_paid_at is not None
```

#### Frontend - Testes Principais

**Arquivo**: `src/pages/Student/Competitions/__tests__/CompetitionSubmitSuccessModal.test.tsx`

```typescript
describe('CompetitionSubmitSuccessModal', () => {
  it('should display coins earned', () => {
    render(<CompetitionSubmitSuccessModal open={true} coinsEarned={50} />);
    
    expect(screen.getByText('+50 moedas!')).toBeInTheDocument();
    expect(screen.getByText(/ganhou.*moedas por participar/i)).toBeInTheDocument();
  });
  
  it('should show animation for coins', () => {
    render(<CompetitionSubmitSuccessModal open={true} coinsEarned={50} />);
    
    const coinElement = screen.getByTestId('coin-animation');
    expect(coinElement).toHaveClass('animate-pulse');
  });
});
```

**Arquivo**: `e2e/competitions/participation-flow.spec.ts` (Cypress)

```typescript
describe('Competition Participation Flow', () => {
  it('should complete full participation flow with coins', () => {
    cy.login('student@test.com', 'password');
    
    // 1. Ver competições disponíveis
    cy.visit('/student/competitions');
    cy.contains('Competição Matemática').should('be.visible');
    
    // 2. Inscrever-se
    cy.contains('Inscrever-se').click();
    cy.contains('Confirmar inscrição').click();
    cy.contains('Inscrição realizada!').should('be.visible');
    
    // 3. Fazer prova
    cy.contains('Fazer prova').click();
    // ... responder questões
    cy.contains('Finalizar prova').click();
    
    // 4. Verificar modal de sucesso com moedas
    cy.contains('+50 moedas!').should('be.visible');
    
    // 5. Verificar saldo atualizado
    cy.get('[data-testid="coin-balance"]').should('contain', '50');
  });
});
```

### Checklist TDD - Etapa 4

- [ ] 🔴 Teste de crédito de moedas ao entregar
- [ ] 🟢 Implementar lógica de pagamento
- [ ] 🔴 Teste de pagamento único
- [ ] 🟢 Implementar controle (CompetitionReward)
- [ ] 🔴 Teste de modal de sucesso
- [ ] 🟢 Implementar modal com animação
- [ ] 🔴 Teste E2E do fluxo completo
- [ ] 🟢 Garantir integração funcionando
- [ ] ✅ Cobertura: backend 80%, frontend 70%

---

## Etapa 5: Ranking e Pagamento de Recompensas

### Objetivo
Calcular ranking ao fim da competição e pagar moedas para as posições premiadas. Exibir ranking para alunos.

### Backend

#### 5.1 Migrations
**Arquivo**: `migrations/versions/add_competition_ranking_payouts.py`

```python
# Tabela: competition_ranking_payouts
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id)
- student_id (String, FK → student.id)
- position (Integer) # 1, 2, 3...
- amount (Integer) # moedas creditadas
- paid_at (TIMESTAMP)
- created_at (TIMESTAMP)
# Constraint: unique(competition_id, student_id)
```

#### 5.2 Services
**Arquivo**: `app/services/competition_ranking_service.py`

```python
class CompetitionRankingService:
    @staticmethod
    def calculate_ranking(competition_id):
        """
        Calcula ranking da competição conforme critério
        Retorna: lista ordenada de {student_id, value, position}
        """
        competition = Competition.query.get(competition_id)
        test_sessions = TestSession.query.filter_by(
            test_id=competition.test_id,
            status='finalizada'
        ).all()
        
        # Ordenar conforme ranking_criteria:
        if competition.ranking_criteria == 'nota':
            sorted_sessions = sorted(test_sessions, key=lambda s: s.grade or 0, reverse=True)
        elif competition.ranking_criteria == 'tempo':
            sorted_sessions = sorted(test_sessions, key=lambda s: s.duration_minutes or 999999)
        elif competition.ranking_criteria == 'acertos':
            sorted_sessions = sorted(test_sessions, key=lambda s: s.correct_answers or 0, reverse=True)
        # ... outros critérios
        
        # Aplicar tiebreaker se necessário
        # ...
        
        # Montar ranking com posições
        ranking = []
        for idx, session in enumerate(sorted_sessions, start=1):
            ranking.append({
                'position': idx,
                'student_id': session.student_id,
                'value': session.grade  # ou tempo, ou acertos
            })
        
        return ranking
    
    @staticmethod
    def pay_ranking_rewards(competition_id):
        """
        Paga moedas para posições premiadas
        """
        competition = Competition.query.get(competition_id)
        ranking = CompetitionRankingService.calculate_ranking(competition_id)
        
        # Ler reward_config
        ranking_rewards = competition.reward_config.get('ranking_rewards', [])
        
        for reward_config in ranking_rewards:
            position = reward_config['position']
            coins = reward_config['coins']
            
            # Buscar aluno naquela posição
            if position <= len(ranking):
                student_id = ranking[position - 1]['student_id']
                
                # Verificar se já pagou
                payout = CompetitionRankingPayout.query.filter_by(
                    competition_id=competition_id,
                    student_id=student_id
                ).first()
                
                if not payout:
                    # Creditar moedas
                    CoinService.credit_coins(
                        student_id=student_id,
                        amount=coins,
                        reason=f'competition_rank_{position}',
                        competition_id=competition_id,
                        description=f"{position}º lugar na competição: {competition.name}"
                    )
                    
                    # Registrar payout
                    payout = CompetitionRankingPayout(
                        competition_id=competition_id,
                        student_id=student_id,
                        position=position,
                        amount=coins,
                        paid_at=datetime.utcnow()
                    )
                    db.session.add(payout)
        
        db.session.commit()
    
    @staticmethod
    def get_ranking(competition_id, limit=100):
        """
        Retorna ranking com dados dos alunos
        """
        ranking = CompetitionRankingService.calculate_ranking(competition_id)
        
        # Enriquecer com dados do aluno (nome, turma, etc.)
        for item in ranking[:limit]:
            student = Student.query.get(item['student_id'])
            item['student_name'] = student.nome if student else 'Desconhecido'
            item['student_class'] = student.class.name if student and student.class else ''
        
        return ranking
```

#### 5.3 Celery Task (Job)
**Arquivo**: `app/services/celery_tasks/competition_tasks.py`

```python
@celery.task
def process_finished_competitions():
    """
    Job que roda periodicamente (ex: a cada hora)
    Processa competições que expiraram e ainda não tiveram ranking pago
    """
    now = datetime.utcnow()
    
    competitions = Competition.query.filter(
        Competition.expiration < now,
        Competition.status.in_(['aberta', 'em_andamento'])
    ).all()
    
    for competition in competitions:
        # Verificar se já pagou ranking
        payouts_count = CompetitionRankingPayout.query.filter_by(
            competition_id=competition.id
        ).count()
        
        if payouts_count == 0:
            # Pagar ranking
            CompetitionRankingService.pay_ranking_rewards(competition.id)
            
            # Atualizar status
            competition.status = 'encerrada'
            db.session.commit()
            
            logger.info(f"Competição {competition.id} encerrada e ranking pago")
```

**Configurar no Celery Beat** (arquivo de configuração):

```python
# celery beat schedule
CELERY_BEAT_SCHEDULE = {
    'process-finished-competitions': {
        'task': 'app.services.celery_tasks.competition_tasks.process_finished_competitions',
        'schedule': crontab(minute='*/60'),  # a cada hora
    },
}
```

#### 5.4 Routes (adicionar em `competition_routes.py`)

```python
# GET /competitions/:id/ranking
# Retorna ranking da competição
# Validações:
#   - Se ranking_visibility = 'realtime': retorna sempre (se houver sessões finalizadas)
#   - Se ranking_visibility = 'final': só retorna se competition.status = 'encerrada'
# Permissões: alunos inscritos, professor/admin
# Retorna: lista de {position, student_name, student_class, value}

# GET /competitions/:id/my-ranking
# Retorna posição do aluno logado no ranking
# Retorna: {position, total_participants, value, coins_earned (se premiado)}
```

### Frontend

#### 5.1 Componente: CompetitionRanking
**Arquivo**: `src/pages/Student/Competitions/CompetitionRanking.tsx`

**Descrição**: Exibe ranking da competição (pode ser componente ou página separada).

**Componentes**:
- **Header**: "Ranking - [Nome da Competição]"
- **Minha posição** (destaque no topo):
  - Card grande: "Você está em [X]º lugar de [Y] participantes"
  - Se premiado: badge "Você ganhou [Z] moedas!"
- **Podium** (top 3):
  - Visual atraente com medalhas (ouro, prata, bronze)
  - Foto/avatar do aluno (se houver), nome, turma
  - Valor (nota/tempo/acertos)
  - Moedas ganhas (ex: "+100 moedas")
- **Lista completa**:
  - Tabela/cards: posição, nome, turma, valor
  - Se ranking_visibility = 'realtime': auto-atualiza a cada X segundos (polling ou websocket)
  - Paginação (se muitos participantes)
- **Filtros** (opcional):
  - Por turma, por escola (se escopo for amplo)

#### 5.2 Adicionar em CompetitionDetailsStudent
**Arquivo**: `src/pages/Student/Competitions/CompetitionDetailsStudent.tsx`

**Seção: Ranking** (atualizar):

```tsx
// Se ranking_visibility = 'realtime' E período de aplicação OU encerrada:
//   - Exibir CompetitionRanking (inline ou link)
//   - Botão "Atualizar ranking" (se tempo real)

// Se ranking_visibility = 'final' E status = 'encerrada':
//   - Exibir CompetitionRanking

// Se não visível ainda:
//   - "Ranking será divulgado após o término da competição"
//   - Countdown até expiration (opcional)
```

#### 5.3 Notificação de prêmio
**Arquivo**: `src/components/Notifications/CompetitionRewardNotification.tsx`

**Descrição**: Quando aluno ganhou moedas de ranking, exibir notificação/toast especial.

**Implementação**:
- Backend pode criar "notificação" ao pagar ranking (tabela de notificações ou websocket)
- Frontend exibe toast/modal: "Parabéns! Você ficou em [X]º lugar na competição [Nome] e ganhou [Y] moedas!"
- Link para ver ranking completo

### Testes (TDD) - Etapa 5

#### Backend - Testes Unitários

**Arquivo**: `tests/unit/services/test_competition_ranking_service.py`

```python
def test_calculate_ranking_by_grade(competition_fixture):
    """Ranking por nota deve ordenar corretamente"""
    # Setup: 3 sessões com notas diferentes
    sessions = [
        TestSession(student_id='s1', test_id=competition_fixture.test_id, grade=8.5),
        TestSession(student_id='s2', test_id=competition_fixture.test_id, grade=9.0),
        TestSession(student_id='s3', test_id=competition_fixture.test_id, grade=7.5),
    ]
    for s in sessions:
        s.status = 'finalizada'
        db.session.add(s)
    db.session.commit()
    
    competition_fixture.ranking_criteria = 'nota'
    
    # Act
    ranking = CompetitionRankingService.calculate_ranking(competition_fixture.id)
    
    # Assert
    assert ranking[0]['student_id'] == 's2'  # 9.0 - 1º
    assert ranking[1]['student_id'] == 's1'  # 8.5 - 2º
    assert ranking[2]['student_id'] == 's3'  # 7.5 - 3º

def test_calculate_ranking_by_time():
    """Ranking por tempo deve ordenar do mais rápido ao mais lento"""
    # 🔴 RED: escrever teste
    # 🟢 GREEN: implementar
    # 🔵 REFACTOR
    pass

def test_pay_ranking_rewards_credits_correct_amounts(competition_fixture):
    """Pagamento de ranking deve creditar valores corretos"""
    # Setup: ranking com 3 alunos
    ranking = [
        {'position': 1, 'student_id': 's1', 'value': 10.0},
        {'position': 2, 'student_id': 's2', 'value': 9.0},
        {'position': 3, 'student_id': 's3', 'value': 8.0},
    ]
    
    competition_fixture.reward_config = {
        'participation_coins': 50,
        'ranking_rewards': [
            {'position': 1, 'coins': 100},
            {'position': 2, 'coins': 50},
            {'position': 3, 'coins': 25}
        ]
    }
    
    # Mock calculate_ranking
    with patch.object(CompetitionRankingService, 'calculate_ranking', return_value=ranking):
        CompetitionRankingService.pay_ranking_rewards(competition_fixture.id)
    
    # Assert: saldos corretos
    assert CoinService.get_balance('s1') == 100
    assert CoinService.get_balance('s2') == 50
    assert CoinService.get_balance('s3') == 25

def test_pay_ranking_rewards_only_once(competition_fixture):
    """Ranking só deve ser pago uma vez"""
    # Pagar primeira vez
    CompetitionRankingService.pay_ranking_rewards(competition_fixture.id)
    
    # Tentar pagar novamente
    CompetitionRankingService.pay_ranking_rewards(competition_fixture.id)
    
    # Verificar que não pagou duas vezes
    payouts = CompetitionRankingPayout.query.filter_by(
        competition_id=competition_fixture.id
    ).all()
    
    assert len(payouts) == 3  # não 6

def test_pay_ranking_rewards_creates_payouts_records():
    """Pagamento deve criar registros em competition_ranking_payouts"""
    # ...
    
    payout = CompetitionRankingPayout.query.filter_by(
        competition_id=competition_fixture.id,
        student_id='s1',
        position=1
    ).first()
    
    assert payout is not None
    assert payout.amount == 100
    assert payout.paid_at is not None
```

#### Backend - Testes de Integração

**Arquivo**: `tests/integration/celery/test_competition_tasks.py`

```python
def test_process_finished_competitions_task(competition_fixture):
    """Job deve processar competições expiradas"""
    # Setup: competição expirada
    competition_fixture.expiration = datetime.utcnow() - timedelta(hours=1)
    competition_fixture.status = 'aberta'
    db.session.commit()
    
    # Act: rodar job
    process_finished_competitions.apply()
    
    # Assert: status atualizado
    competition_fixture = Competition.query.get(competition_fixture.id)
    assert competition_fixture.status == 'encerrada'
    
    # Assert: ranking pago
    payouts = CompetitionRankingPayout.query.filter_by(
        competition_id=competition_fixture.id
    ).count()
    assert payouts > 0

def test_job_does_not_process_same_competition_twice():
    """Job não deve processar competição já encerrada"""
    # Já processada
    competition = Competition(status='encerrada', expiration=datetime.utcnow() - timedelta(days=1))
    
    process_finished_competitions.apply()
    
    # Verificar que não tentou processar novamente
    # (mockar pay_ranking_rewards e verificar que não foi chamado)
```

**Arquivo**: `tests/integration/routes/test_competition_ranking_routes.py`

```python
def test_get_ranking_endpoint_realtime(client, student_headers, competition_fixture):
    """GET /competitions/:id/ranking deve retornar ranking (realtime)"""
    competition_fixture.ranking_visibility = 'realtime'
    
    response = client.get(f'/competitions/{competition_fixture.id}/ranking',
        headers=student_headers
    )
    
    assert response.status_code == 200
    assert 'ranking' in response.json

def test_get_ranking_endpoint_final_only_after_expiration(client, student_headers, competition_fixture):
    """Ranking 'final' só deve ser visível após expiração"""
    competition_fixture.ranking_visibility = 'final'
    competition_fixture.expiration = datetime.utcnow() + timedelta(days=1)  # ainda não expirou
    
    response = client.get(f'/competitions/{competition_fixture.id}/ranking',
        headers=student_headers
    )
    
    assert response.status_code == 403
    assert 'ainda não disponível' in response.json['message'].lower()
```

#### Frontend - Testes Principais

**Arquivo**: `src/pages/Student/Competitions/__tests__/CompetitionRanking.test.tsx`

```typescript
describe('CompetitionRanking', () => {
  it('should display top 3 podium', async () => {
    server.use(
      rest.get('/competitions/:id/ranking', (req, res, ctx) => {
        return res(ctx.json({
          ranking: [
            { position: 1, student_name: 'Alice', value: 10.0 },
            { position: 2, student_name: 'Bob', value: 9.5 },
            { position: 3, student_name: 'Carol', value: 9.0 },
          ]
        }));
      })
    );
    
    render(<CompetitionRanking competitionId="comp-123" />);
    
    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.getByText('Carol')).toBeInTheDocument();
    });
    
    // Verificar medalhas
    expect(screen.getByTestId('medal-gold')).toBeInTheDocument();
    expect(screen.getByTestId('medal-silver')).toBeInTheDocument();
    expect(screen.getByTestId('medal-bronze')).toBeInTheDocument();
  });
  
  it('should display student position', async () => {
    render(<CompetitionRanking competitionId="comp-123" />);
    
    await waitFor(() => {
      expect(screen.getByText(/você está em.*5º lugar/i)).toBeInTheDocument();
    });
  });
  
  it('should auto-refresh if realtime visibility', async () => {
    jest.useFakeTimers();
    
    render(<CompetitionRanking competitionId="comp-123" rankingVisibility="realtime" />);
    
    // Avançar 10 segundos
    jest.advanceTimersByTime(10000);
    
    // Verificar que fez nova requisição
    await waitFor(() => {
      expect(screen.getByText('Atualizado agora')).toBeInTheDocument();
    });
    
    jest.useRealTimers();
  });
});
```

### Checklist TDD - Etapa 5

- [ ] 🔴 Testes de cálculo de ranking (nota, tempo, acertos)
- [ ] 🟢 Implementar cálculo com critérios
- [ ] 🔴 Testes de pagamento de ranking
- [ ] 🟢 Implementar pagamento com reward_config
- [ ] 🔴 Testes de job de processamento
- [ ] 🟢 Implementar Celery task
- [ ] 🔴 Testes de endpoints de ranking
- [ ] 🟢 Implementar routes com validações
- [ ] 🔴 Testes frontend (ranking, podium)
- [ ] 🟢 Implementar UI de ranking
- [ ] 🔴 Testes de auto-refresh (realtime)
- [ ] 🟢 Implementar polling/websocket
- [ ] ✅ Cobertura: backend 80%, frontend 70%

---

## Etapa 6: Templates e Criação Automática

### Objetivo
Criar sistema de templates para competições recorrentes. Job automático lê templates e cria competições conforme periodicidade (semanal, quinzenal, mensal).

### Backend

#### 6.1 Migrations
**Arquivo**: `migrations/versions/add_competition_templates.py`

```python
# Tabela: competition_templates
- id (String/UUID, PK)
- name (String, required) # nome do template
- subject_id (String, FK → subject.id)
- level (Integer)
- scope (String, default='individual')
- scope_filter (JSON, nullable)
- recurrence (String, required) # weekly, biweekly, monthly
- question_mode (String, default='auto_random')
- question_rules (JSON)
- reward_config (JSON)
- ranking_criteria (String, default='nota')
- ranking_tiebreaker (String, default='tempo_entrega')
- ranking_visibility (String, default='final')
- max_participants (Integer, nullable)
- active (Boolean, default=True) # se false, não cria novas competições
- created_by (String, FK → users.id)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### 6.2 Models
**Arquivo**: `app/models/competitionTemplate.py`

```python
class CompetitionTemplate(db.Model):
    # Campos conforme migration
    # Relacionamentos:
    - subject
    - creator
    - competitions (lista de competições criadas deste template)
    
    # Métodos:
    def generate_competition_for_period(self, start_date):
        """
        Gera uma competição baseada neste template para um período específico
        Retorna: Competition criada
        """
        # Calcular datas:
        # - enrollment_start, enrollment_end (ex: segunda 00h - quarta 23h59)
        # - application, expiration (ex: quinta 00h - domingo 23h59)
        # Criar competition com dados do template
```

#### 6.3 Routes
**Arquivo**: `app/routes/competition_template_routes.py`

```python
# POST /competition-templates/
# Cria template (admin/coordenador)
# Body: todos os campos do template
# Retorna: template criado

# GET /competition-templates/
# Lista templates (admin/coordenador)
# Query params: ?active=true, ?subject_id=xxx
# Retorna: lista de templates

# GET /competition-templates/:id
# Detalhes de um template
# Retorna: template + lista de competições criadas

# PATCH /competition-templates/:id
# Atualiza template
# Nota: não afeta competições já criadas, só futuras
# Retorna: template atualizado

# DELETE /competition-templates/:id
# Deleta template (ou apenas desativa: active=false)
# Retorna: sucesso

# POST /competition-templates/:id/deactivate
# Desativa template (para de criar competições)
# Retorna: template com active=false

# POST /competition-templates/:id/activate
# Ativa template (volta a criar competições)
# Retorna: template com active=true
```

#### 6.4 Celery Task (Job)
**Arquivo**: `app/services/celery_tasks/competition_tasks.py`

```python
@celery.task
def create_competitions_from_templates():
    """
    Job que roda diariamente (ex: todo dia às 00:00)
    Cria competições para a semana/quinzena/mês se ainda não existir
    """
    now = datetime.utcnow()
    
    templates = CompetitionTemplate.query.filter_by(active=True).all()
    
    for template in templates:
        # Verificar periodicidade
        if template.recurrence == 'weekly':
            # Verificar se já existe competição para esta semana
            start_of_week = now - timedelta(days=now.weekday())  # segunda-feira
            existing = Competition.query.filter(
                Competition.template_id == template.id,
                Competition.enrollment_start >= start_of_week,
                Competition.enrollment_start < start_of_week + timedelta(days=7)
            ).first()
            
            if not existing:
                # Criar competição para esta semana
                competition = template.generate_competition_for_period(start_of_week)
                db.session.add(competition)
                logger.info(f"Competição criada do template {template.id}: {competition.name}")
        
        elif template.recurrence == 'biweekly':
            # Lógica similar para quinzenal
            pass
        
        elif template.recurrence == 'monthly':
            # Lógica similar para mensal
            pass
    
    db.session.commit()
```

**Configurar no Celery Beat**:

```python
CELERY_BEAT_SCHEDULE = {
    'create-competitions-from-templates': {
        'task': 'app.services.celery_tasks.competition_tasks.create_competitions_from_templates',
        'schedule': crontab(hour=0, minute=0),  # todo dia à meia-noite
    },
    # ... outros jobs
}
```

### Frontend

#### 6.1 Página: CompetitionTemplateList
**Arquivo**: `src/pages/Admin/Competitions/CompetitionTemplateList.tsx`

**Rota**: `/admin/competition-templates`

**Descrição**: Lista de templates de competições recorrentes.

**Componentes**:
- **Header**: "Templates de Competições" + botão "Novo Template"
- **Filtros**: por disciplina, por periodicidade, por status (ativo/inativo)
- **Tabela/Cards**:
  - Nome do template
  - Disciplina | Nível | Escopo
  - Periodicidade (badge: Semanal, Quinzenal, Mensal)
  - Status (ativo/inativo)
  - Última competição criada (data)
  - Próxima criação (estimativa)
  - Ações: Ver, Editar, Ativar/Desativar, Excluir

#### 6.2 Modal/Página: CreateTemplateModal
**Arquivo**: `src/pages/Admin/Competitions/CreateTemplateModal.tsx`

**Descrição**: Formulário de criação de template (similar a CreateCompetitionModal, mas sem datas específicas).

**Campos**:
- Nome do template (ex: "Competição Semanal Matemática Nível 1")
- Disciplina
- Nível
- Escopo (+ filtros)
- Periodicidade (select: Semanal, Quinzenal, Mensal)
- Modo de questões (auto/manual - se manual, definir pool de questões ou sortear a cada criação)
- Recompensas (participação + ranking)
- Critério de ranking
- Visibilidade de ranking
- Limite de participantes
- **Configuração de datas** (relativas):
  - "Inscrição abre na segunda-feira às 00:00 e fecha na quarta-feira às 23:59"
  - "Aplicação abre na quinta-feira às 00:00 e fecha no domingo às 23:59"
  - (ou interface mais flexível com offsets)

#### 6.3 Página: TemplateDetails
**Arquivo**: `src/pages/Admin/Competitions/TemplateDetails.tsx`

**Rota**: `/admin/competition-templates/:id`

**Descrição**: Detalhes do template + lista de competições criadas.

**Componentes**:
- **Seção: Configuração do template** (igual a competição)
- **Seção: Competições criadas** (lista de todas as competições geradas deste template):
  - Nome, datas, status, inscritos, etc.
  - Link para ver competição
- **Botões**:
  - Editar template
  - Ativar/Desativar
  - Excluir template (confirmar em modal)

### Testes (TDD) - Etapa 6

#### Testes Principais (resumido)

```python
# Backend
def test_template_generates_competition_weekly():
    """Template semanal deve gerar competição toda semana"""
    template = CompetitionTemplate(recurrence='weekly', active=True)
    
    # Rodar job
    create_competitions_from_templates.apply()
    
    # Verificar competição criada
    competitions = Competition.query.filter_by(template_id=template.id).all()
    assert len(competitions) == 1

def test_template_does_not_create_duplicate_competitions():
    """Não deve criar duas competições para mesma semana"""
    # Já existe competição desta semana
    # Rodar job novamente
    # Verificar que não criou duplicata

def test_deactivated_template_does_not_create_competitions():
    """Template desativado não cria novas competições"""
    template = CompetitionTemplate(recurrence='weekly', active=False)
    # ...

# Frontend
describe('CompetitionTemplateList', () => {
  it('should display template list', () => { /* ... */ });
  it('should create new template', () => { /* ... */ });
  it('should toggle template active status', () => { /* ... */ });
});
```

### Checklist TDD - Etapa 6

- [ ] 🔴 Testes de criação de template
- [ ] 🟢 Implementar templates CRUD
- [ ] 🔴 Testes de job de criação automática
- [ ] 🟢 Implementar job com periodicidade
- [ ] 🔴 Testes de não-duplicação
- [ ] 🟢 Implementar verificação de existência
- [ ] 🔴 Testes frontend
- [ ] 🟢 Implementar UI de templates
- [ ] ✅ Cobertura: backend 80%, frontend 70%

---

## Etapa 7: Funcionalidades Avançadas

### Objetivo
Implementar funcionalidades avançadas: ranking em tempo real (websocket/polling), escopo detalhado (turma/escola/município), notificações, loja de moedas (futuro), etc.

### Backend

#### 7.1 Ranking em tempo real (WebSocket ou Polling)

**Opção A: Polling** (mais simples)
- Frontend chama `GET /competitions/:id/ranking` a cada X segundos
- Backend retorna ranking atualizado
- Já funciona com endpoint existente (Etapa 5)

**Opção B: WebSocket** (mais elegante)
- Usar Flask-SocketIO ou similar
- Evento: `join_competition_ranking` (aluno entra na "sala" da competição)
- Evento: `ranking_updated` (servidor envia novo ranking quando alguém entrega prova)
- Implementação:

```python
# socketio.py
from flask_socketio import SocketIO, emit, join_room

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('join_competition_ranking')
def on_join_ranking(data):
    competition_id = data['competition_id']
    join_room(f"competition_{competition_id}")
    # Enviar ranking atual
    ranking = CompetitionRankingService.get_ranking(competition_id)
    emit('ranking_updated', {'ranking': ranking}, room=f"competition_{competition_id}")

# Ao finalizar prova de competição (no fluxo de entrega):
def notify_ranking_updated(competition_id):
    ranking = CompetitionRankingService.get_ranking(competition_id)
    socketio.emit('ranking_updated', {'ranking': ranking}, room=f"competition_{competition_id}")
```

#### 7.2 Notificações

**Adicionar notificações para**:
- Competição aberta para inscrição (no nível/escopo do aluno)
- Inscrição confirmada
- Lembrete: prova abre em 24h
- Lembrete: prova fecha em 2h
- Prova entregue + moedas ganhas
- Ranking divulgado + posição final
- Prêmio de ranking (se ganhou moedas)

**Implementação**:
- Criar sistema de notificações in-app (tabela `notifications`) ou usar existente
- Push notifications (opcional, via Firebase ou similar)

#### 7.3 Escopo detalhado (validações)

**Já implementado nas etapas anteriores**, mas revisar:
- Filtro correto ao listar competições disponíveis
- Validação ao inscrever (verificar turma/escola/município do aluno)
- Ranking filtrado por escopo (se escopo = escola, só alunos daquela escola)

#### 7.4 Loja de moedas (futuro)

**Planejamento** (não implementar agora, mas preparar):
- Tabela `shop_items` (itens da loja: avatares, badges, benefícios)
- Tabela `shop_purchases` (compras do aluno)
- Endpoint `POST /shop/purchase` (debita moedas, registra compra)
- Frontend: página de loja

**Preparação**:
- `coin_transactions` já suporta `amount` negativo (débito)
- `CoinService.debit_coins()` já existe (Etapa 1)

#### 7.5 Relatórios e Analytics (admin)

**Endpoint**: `GET /competitions/:id/analytics`

**Retorna**:
- Taxa de inscrição (inscritos / alunos elegíveis)
- Taxa de participação (entregaram prova / inscritos)
- Média de nota/tempo/acertos
- Distribuição de notas (gráfico)
- Top 10 alunos
- Comparação com competições anteriores

**Frontend**: página de analytics da competição (gráficos com Chart.js ou similar)

### Frontend

#### 7.1 Ranking em tempo real
**Arquivo**: `src/pages/Student/Competitions/CompetitionRanking.tsx`

**Adicionar**:
- Hook `useWebSocket` ou `usePolling` conforme implementação backend
- Auto-atualização do ranking a cada X segundos (se ranking_visibility = 'realtime')
- Indicador visual "Atualizando..." ou "Última atualização: há 5s"

#### 7.2 Notificações
**Arquivo**: `src/components/Notifications/NotificationBell.tsx`

**Adicionar**:
- Badge no ícone de sino (quantidade de notificações não lidas)
- Dropdown com lista de notificações
- Tipo específico: "Competição" (ícone de troféu)
- Click na notificação: redireciona para competição

#### 7.3 Página: CompetitionAnalytics (Admin)
**Arquivo**: `src/pages/Admin/Competitions/CompetitionAnalytics.tsx`

**Rota**: `/admin/competitions/:id/analytics`

**Componentes**:
- **Gráficos**:
  - Pizza: taxa de inscrição, taxa de participação
  - Barra: distribuição de notas
  - Linha: evolução do ranking (tempo real)
- **Métricas**:
  - Cards: inscritos, participantes, média de nota, etc.
- **Tabela**: top 10 alunos

#### 7.4 Filtros avançados
**Arquivo**: `src/pages/Student/Competitions/CompetitionListStudent.tsx`

**Adicionar filtros**:
- Por disciplina (já existe)
- Por recompensas (mínimo de moedas)
- Por vagas (só com vagas disponíveis)
- Por data (próximas semanas)

#### 7.5 Countdown timers
**Componente**: `src/components/Competitions/CompetitionCountdown.tsx`

**Descrição**: Exibe countdown para eventos da competição.

**Uso**:
- "Inscrição fecha em: 2d 5h 30m"
- "Prova abre em: 1d 12h"
- "Prova fecha em: 3h 45m"

### Testes (TDD) - Etapa 7

#### Testes Principais (resumido)

```python
# Backend - WebSocket
def test_websocket_ranking_updates():
    """WebSocket deve emitir atualizações de ranking"""
    # Conectar cliente websocket
    # Finalizar prova de aluno
    # Verificar que evento 'ranking_updated' foi emitido

# Backend - Notificações
def test_notification_sent_when_competition_opens():
    """Notificação deve ser enviada quando competição abre"""
    # ...

# Backend - Performance
def test_ranking_pagination_with_1000_participants():
    """Ranking deve paginar corretamente com muitos participantes"""
    # Criar 1000 sessões
    # Buscar ranking com limit=100
    # Verificar performance < 1s

# Frontend - Realtime
describe('RealtimeRanking', () => {
  it('should update automatically with websocket', () => {
    // Mock websocket
    // Simular evento de atualização
    // Verificar que ranking foi atualizado
  });
});

# Frontend - Analytics
describe('CompetitionAnalytics', () => {
  it('should display charts correctly', () => { /* ... */ });
  it('should calculate metrics accurately', () => { /* ... */ });
});

# E2E - Performance
describe('Performance Tests', () => {
  it('should load ranking with 500 participants in < 2s', () => {
    cy.visit('/competitions/comp-123/ranking');
    cy.get('[data-testid="ranking-list"]').should('be.visible');
    // Verificar tempo de carregamento
  });
});
```

### Checklist TDD - Etapa 7

- [ ] 🔴 Testes de websocket/polling
- [ ] 🟢 Implementar realtime ranking
- [ ] 🔴 Testes de notificações
- [ ] 🟢 Implementar sistema de notificações
- [ ] 🔴 Testes de performance
- [ ] 🟢 Otimizar queries e paginação
- [ ] 🔴 Testes de analytics
- [ ] 🟢 Implementar gráficos e métricas
- [ ] ✅ Cobertura: backend 80%, frontend 70%

---

## Boas Práticas de TDD

### Princípios Fundamentais

#### 1. Escrever o teste primeiro (sempre!)
- ❌ **Errado**: Implementar código e depois testar
- ✅ **Certo**: Escrever teste, ver falhar, implementar, ver passar

#### 2. Um teste por vez
- Escrever um teste
- Fazer passar
- Refatorar
- Repetir

#### 3. Testes pequenos e específicos
- Cada teste deve testar **uma** coisa
- Nome do teste deve descrever **o quê** e **por quê**
- Formato: `test_<ação>_<contexto>_<resultado_esperado>`

```python
# ✅ BOM
def test_enroll_student_fails_when_no_slots_available():
    """Deve falhar ao inscrever quando vagas esgotadas"""
    # ...

# ❌ RUIM
def test_enrollment():
    """Testa inscrição"""
    # testa múltiplas coisas...
```

#### 4. Testes independentes
- Cada teste deve rodar isoladamente
- Não depender de ordem de execução
- Setup e teardown corretos (fixtures)

#### 5. Arrange-Act-Assert (AAA)
```python
def test_credit_coins_increases_balance():
    # Arrange (preparar)
    student = Student(nome='Test')
    initial_balance = 0
    
    # Act (executar)
    CoinService.credit_coins(student.id, 50, 'test')
    
    # Assert (verificar)
    assert CoinService.get_balance(student.id) == 50
```

### Erros Comuns e Como Evitar

#### ❌ Testar implementação em vez de comportamento
```python
# RUIM: teste frágil, quebra se mudar implementação
def test_credit_coins_calls_session_add():
    with patch('db.session.add') as mock_add:
        CoinService.credit_coins(student_id, 50, 'test')
        mock_add.assert_called_once()

# BOM: testa comportamento final
def test_credit_coins_increases_balance():
    balance_before = CoinService.get_balance(student_id)
    CoinService.credit_coins(student_id, 50, 'test')
    balance_after = CoinService.get_balance(student_id)
    assert balance_after == balance_before + 50
```

#### ❌ Testes muito grandes
```python
# RUIM: testa muita coisa
def test_competition_flow():
    # cria competição
    # inscreve aluno
    # faz prova
    # verifica ranking
    # verifica moedas
    # ... 100 linhas

# BOM: dividir em testes menores
def test_create_competition(): ...
def test_enroll_student(): ...
def test_submit_test(): ...
```

#### ❌ Pular o Red (não ver teste falhar)
- Sempre rodar teste antes de implementar
- Confirmar que falha pelo motivo certo
- Se não falhar, o teste pode estar errado

#### ❌ Setup/Teardown inadequado
```python
# RUIM: dados compartilhados entre testes
student = Student(nome='Test')  # global

def test_a():
    student.balance = 100  # muda estado

def test_b():
    assert student.balance == 0  # falha se test_a rodar antes!

# BOM: fixture isolada
@pytest.fixture
def student_fixture():
    student = Student(nome='Test')
    db.session.add(student)
    db.session.commit()
    yield student
    db.session.delete(student)
    db.session.commit()
```

### Quando Usar Mocks

#### ✅ Usar mocks para:
- APIs externas (não chamar serviços reais)
- Banco de dados em testes unitários
- Funções custosas (processamento pesado)
- Testar casos de erro (simular falhas)

```python
def test_external_api_failure():
    with patch('requests.get') as mock_get:
        mock_get.side_effect = ConnectionError('API down')
        
        with pytest.raises(ServiceUnavailableError):
            CompetitionService.fetch_questions_from_api()
```

#### ❌ NÃO usar mocks para:
- Testar lógica interna (testar comportamento real)
- Testes de integração (deixar usar DB de teste)
- Testes E2E (fluxo completo real)

### Cobertura de Código

#### Comandos
```bash
# Backend (pytest)
pytest --cov=app --cov-report=html --cov-report=term

# Frontend (Jest)
npm test -- --coverage --watchAll=false
```

#### Interpretando cobertura
- **80%+**: bom (MVP deve ter isso)
- **90%+**: excelente (código crítico: pagamentos, ranking)
- **100%**: raramente necessário (pode indicar over-testing)

#### O que NÃO está coberto (e tudo bem):
- Código gerado automaticamente
- Configurações e constantes
- Logs e prints
- Código de terceiros

### Pirâmide de Testes

```
        /\
       /  \  E2E (poucos, críticos)
      /____\
     /      \  Integração (moderado)
    /________\
   /          \ Unitários (muitos, rápidos)
  /__________/
```

**Distribuição ideal**:
- 70% unitários (rápidos, isolados)
- 20% integração (componentes juntos)
- 10% E2E (fluxo completo)

### Ferramentas de Qualidade

#### Backend
```bash
# Linter (PEP8)
flake8 app/ tests/

# Type checking
mypy app/

# Security
bandit -r app/

# Complexity
radon cc app/ -a
```

#### Frontend
```bash
# Linter
npm run lint

# Type checking (TypeScript)
npm run type-check

# Test quality
npm run test -- --coverage --verbose
```

### Checklist de Qualidade do Teste

Antes de commitar, verificar:

- [ ] Teste tem nome descritivo
- [ ] Segue padrão AAA (Arrange-Act-Assert)
- [ ] Testa apenas uma coisa
- [ ] Não depende de outros testes
- [ ] Usa fixtures/mocks apropriadamente
- [ ] Passa consistentemente (não flaky)
- [ ] É rápido (< 1s para unitário)
- [ ] Documenta edge cases
- [ ] Cobre casos de sucesso E falha

### Revisão de Código (Code Review) com TDD

Ao revisar PR, verificar:

1. **Testes novos foram adicionados?**
   - Cada feature nova deve ter testes

2. **Testes passam no CI?**
   - GitHub Actions / GitLab CI deve estar verde

3. **Cobertura não diminuiu?**
   - PR não deve reduzir % de cobertura

4. **Testes são de qualidade?**
   - Não apenas "passar por passar"
   - Testam casos reais e edge cases

5. **Red-Green-Refactor foi seguido?**
   - Commits mostram TDD? (teste → impl → refactor)

---

## Resumo de Prioridades

### MVP (Mínimo Viável)
- ✅ Etapa 1: Sistema de Moedas
- ✅ Etapa 2: Competições CRUD
- ✅ Etapa 3: Inscrição e Listagem
- ✅ Etapa 4: Aplicação e Entrega
- ✅ Etapa 5: Ranking e Pagamento

**Com essas 5 etapas, o sistema já funciona end-to-end**: criar competição, aluno se inscrever, fazer prova, ganhar moedas, ver ranking.

### Incrementos (Após MVP)
- ⏭️ Etapa 6: Templates e Criação Automática (competições recorrentes)
- ⏭️ Etapa 7: Funcionalidades Avançadas (ranking em tempo real, notificações, analytics)

---

## Tecnologias e Dependências

### Backend
- **Flask** (já existe)
- **SQLAlchemy** (já existe)
- **Celery** (já existe, para jobs)
- **Flask-SocketIO** (opcional, para ranking em tempo real via websocket)

### Frontend
- **React** (assumindo, ajustar se for Vue/Angular)
- **React Router** (navegação)
- **Axios** (API calls)
- **React Query** ou **SWR** (cache e refetch automático)
- **Socket.io-client** (se usar websocket)
- **Chart.js** ou **Recharts** (gráficos de analytics)
- **date-fns** ou **moment.js** (manipulação de datas, countdown)
- **React Toastify** ou similar (notificações/toasts)

---

## Checklist Final de Implementação (com TDD)

### Etapa 1: Sistema de Moedas
#### Backend
- [ ] 🔴 Escrever testes unitários (CoinService)
- [ ] 🟢 Criar migrations (student_coins, coin_transactions)
- [ ] 🟢 Implementar models (StudentCoins, CoinTransaction)
- [ ] 🟢 Implementar CoinService
- [ ] 🔵 Refatorar services
- [ ] 🔴 Escrever testes de integração (routes)
- [ ] 🟢 Implementar routes (/coins/*)
- [ ] 🔵 Refatorar routes
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (CoinBalance, CoinHistory)
- [ ] 🟢 Implementar CoinBalance component
- [ ] 🟢 Implementar CoinHistory page
- [ ] 🟢 Integrar no header/navbar
- [ ] 🔵 Refatorar componentes
- [ ] 🔴 Escrever testes E2E (Cypress)
- [ ] 🟢 Garantir fluxo E2E funcionando
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 2: Competições CRUD
#### Backend
- [ ] 🔴 Escrever testes unitários (CompetitionService)
- [ ] 🟢 Criar migration (competitions)
- [ ] 🟢 Implementar Competition model
- [ ] 🟢 Implementar CompetitionService
- [ ] 🔵 Refatorar service
- [ ] 🔴 Escrever testes de integração
- [ ] 🟢 Implementar routes CRUD
- [ ] 🔵 Refatorar routes
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (modals, lista)
- [ ] 🟢 Implementar CompetitionList (admin)
- [ ] 🟢 Implementar CreateCompetitionModal
- [ ] 🟢 Implementar CompetitionDetails
- [ ] 🔵 Refatorar componentes
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 3: Inscrição e Listagem
#### Backend
- [ ] 🔴 Escrever testes (filtros, inscrição)
- [ ] 🟢 Implementar filtros de competições disponíveis
- [ ] 🟢 Implementar enroll/unenroll endpoints
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (lista aluno, modal inscrição)
- [ ] 🟢 Implementar CompetitionListStudent
- [ ] 🟢 Implementar EnrollConfirmationModal
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 4: Aplicação e Entrega
#### Backend
- [ ] 🔴 Escrever testes (pagamento participação)
- [ ] 🟢 Criar migration (competition_rewards)
- [ ] 🟢 Implementar lógica de pagamento na finalização
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (modal sucesso, botões)
- [ ] 🟢 Implementar botão "Fazer prova"
- [ ] 🟢 Implementar CompetitionSubmitSuccessModal
- [ ] 🔵 Refatorar
- [ ] 🔴 Escrever teste E2E (fluxo completo)
- [ ] 🟢 Garantir fluxo E2E funcionando
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 5: Ranking e Pagamento
#### Backend
- [ ] 🔴 Escrever testes (cálculo ranking)
- [ ] 🟢 Criar migration (competition_ranking_payouts)
- [ ] 🟢 Implementar CompetitionRankingService
- [ ] 🔵 Refatorar service
- [ ] 🔴 Escrever testes (job Celery)
- [ ] 🟢 Implementar Celery task
- [ ] 🔴 Escrever testes (routes ranking)
- [ ] 🟢 Implementar routes
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (ranking, podium)
- [ ] 🟢 Implementar CompetitionRanking
- [ ] 🔵 Refatorar
- [ ] 🔴 Teste de auto-refresh (realtime)
- [ ] 🟢 Implementar polling/websocket
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 6: Templates
#### Backend
- [ ] 🔴 Escrever testes (template, job)
- [ ] 🟢 Criar migration (competition_templates)
- [ ] 🟢 Implementar template CRUD
- [ ] 🟢 Implementar Celery task (criação automática)
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Escrever testes (CRUD templates)
- [ ] 🟢 Implementar TemplateList
- [ ] 🟢 Implementar CreateTemplateModal
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 70%

### Etapa 7: Avançadas
#### Backend
- [ ] 🔴 Testes (websocket, notificações, performance)
- [ ] 🟢 Implementar funcionalidades avançadas
- [ ] 🔵 Refatorar e otimizar
- [ ] ✅ Cobertura: ≥ 80%

#### Frontend
- [ ] 🔴 Testes (realtime, analytics)
- [ ] 🟢 Implementar features avançadas
- [ ] 🔵 Refatorar
- [ ] ✅ Cobertura: ≥ 70%

### Validação de Qualidade (em cada etapa)
- [ ] CI/CD passando (GitHub Actions / GitLab CI)
- [ ] Cobertura de testes atingida (80% backend, 70% frontend)
- [ ] Linters sem erros (flake8, eslint)
- [ ] Code review aprovado
- [ ] Documentação atualizada
- [ ] Testes E2E dos fluxos principais passando

---

**Observação**: Este plano segue rigorosamente **TDD** (Test-Driven Development). Cada funcionalidade deve ter seus testes escritos ANTES da implementação, seguindo o ciclo 🔴 Red → 🟢 Green → 🔵 Refactor. Cada etapa é incremental e depende das anteriores. Validar completamente cada etapa (incluindo cobertura de testes) antes de prosseguir para a próxima.

---

## Benefícios do TDD neste Projeto

### 1. **Confiança nas mudanças**
- Ao adicionar novas features (Etapas 6 e 7), os testes das etapas 1-5 garantem que nada quebrou
- Refatorações são seguras (se testes passam, comportamento está preservado)

### 2. **Documentação viva**
- Testes servem como documentação de como usar os componentes
- Exemplo: `test_enroll_student_fails_if_no_slots_available()` documenta que inscrição respeita limite de vagas

### 3. **Design melhor**
- TDD força a pensar na interface antes da implementação
- Código testável tende a ser mais modular e desacoplado

### 4. **Menos bugs em produção**
- Bugs encontrados em desenvolvimento, não por usuários
- Edge cases cobertos desde o início

### 5. **Facilita onboarding**
- Novos desenvolvedores podem rodar testes para entender o sistema
- Alterações têm rede de segurança

### 6. **CI/CD confiável**
- Pipeline automatizado valida cada commit
- Deploy só acontece se todos os testes passarem

### Comandos Úteis

```bash
# Backend - rodar testes
pytest                                    # todos os testes
pytest tests/unit/                        # só unitários
pytest tests/integration/                 # só integração
pytest -k "test_coin"                     # só testes de moedas
pytest --cov=app --cov-report=html        # com cobertura
pytest -v                                 # verbose
pytest --lf                               # last failed (re-run falhas)

# Frontend - rodar testes
npm test                                  # modo watch
npm test -- --coverage                    # com cobertura
npm test -- --watch=false                 # run once
npm test -- CoinBalance                   # só CoinBalance

# E2E - Cypress
npm run cypress:open                      # modo interativo
npm run cypress:run                       # headless (CI)
```

### Próximos Passos

1. **Setup inicial**: configurar ambiente de testes (conftest.py, setupTests.js)
2. **Etapa 1 completa**: seguir TDD rigorosamente, estabelecer padrões
3. **Etapas 2-5**: manter disciplina TDD, aumentar cobertura
4. **Etapas 6-7**: adicionar testes de performance e stress
5. **Manutenção**: manter testes atualizados, refatorar quando necessário

**Lembre-se**: TDD é um investimento. Leva mais tempo no início, mas economiza muito tempo em bugs e refatorações futuras. 🚀

---

## Arquivos Separados

Para implementação detalhada, consulte os planos específicos:

### 📘 Backend - [PLANO_IMPLEMENTACAO_BACKEND.md](./PLANO_IMPLEMENTACAO_BACKEND.md)

Contém:
- ✅ Migrations completas (todas as tabelas)
- ✅ Models (StudentCoins, CoinTransaction, Competition, etc.)
- ✅ Services (CoinService, CompetitionService, CompetitionRankingService)
- ✅ Routes (endpoints REST completos)
- ✅ Celery Tasks (jobs automáticos)
- ✅ Testes unitários, integração e E2E (pytest)
- ✅ Checklist TDD por etapa

**Tecnologias**: Flask, SQLAlchemy, Celery, pytest, Flask-SocketIO

### 📗 Frontend - [PLANO_IMPLEMENTACAO_FRONTEND.md](./PLANO_IMPLEMENTACAO_FRONTEND.md)

Contém:
- ✅ Componentes (CoinBalance, CompetitionCard, etc.)
- ✅ Páginas (CoinHistory, CompetitionList, CompetitionRanking)
- ✅ Modais (CreateCompetitionModal, EnrollConfirmationModal, etc.)
- ✅ Rotas e navegação
- ✅ Testes unitários, integração e E2E (Jest, RTL, Cypress)
- ✅ Checklist TDD por etapa

**Tecnologias**: React, React Router, Axios, Jest, React Testing Library, Cypress, MSW

---

## Roadmap de Implementação

### Fase 1: MVP (Etapas 1-5) - 4-6 semanas
- ✅ Sistema completo de competições funcional
- ✅ Alunos podem se inscrever e participar
- ✅ Moedas e ranking funcionando
- ✅ Testes com 80%/70% cobertura

### Fase 2: Automação (Etapa 6) - 2-3 semanas
- ✅ Templates e criação automática
- ✅ Competições recorrentes semanais/mensais
- ✅ Testes de jobs automáticos

### Fase 3: Avançadas (Etapa 7) - 3-4 semanas
- ✅ Ranking em tempo real
- ✅ Notificações
- ✅ Analytics e relatórios
- ✅ Otimizações de performance

**Total estimado**: 9-13 semanas (com TDD completo)

---

## Links Rápidos

- 📘 [Plano Backend](./PLANO_IMPLEMENTACAO_BACKEND.md)
- 📗 [Plano Frontend](./PLANO_IMPLEMENTACAO_FRONTEND.md)
- 📄 [Especificação do Sistema](./SISTEMA_COMPETICOES.md)
- 🗂️ [Tabelas e Estrutura](./SISTEMA_COMPETICOES.md#5-estrutura-das-tabelas-campos-principais)
