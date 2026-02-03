# Plano de Implementação - Backend (Sistema de Competições)

Plano de implementação focado no backend do sistema de competições.

---

## Índice

1. [Etapa 1: Sistema de Moedas](#etapa-1-sistema-de-moedas)
2. [Etapa 2: Competições CRUD](#etapa-2-competições-crud)
3. [Etapa 3: Inscrição e Listagem](#etapa-3-inscrição-e-listagem)
4. [Etapa 4: Aplicação e Entrega](#etapa-4-aplicação-e-entrega)
5. [Etapa 5: Ranking e Pagamento](#etapa-5-ranking-e-pagamento)
6. [Etapa 6: Templates e Criação Automática](#etapa-6-templates-e-criação-automática)
7. [Etapa 7: Funcionalidades Avançadas](#etapa-7-funcionalidades-avançadas)
8. [Checklist Final](#checklist-final)

---

## Etapa 1: Sistema de Moedas

### Objetivo
Criar infraestrutura básica de moedas: saldo, transações e histórico.

### 1.1 Migrations

**Arquivo**: `migrations/versions/add_student_coins_system.py`

```python
def upgrade():
    # Tabela: student_coins
    op.create_table('student_coins',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('balance', sa.Integer(), default=0),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id']),
        sa.UniqueConstraint('student_id', name='uq_student_coins_student_id')
    )

    # Tabela: coin_transactions
    op.create_table('coin_transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('student_id', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_before', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('competition_id', sa.String(), nullable=True),
        sa.Column('test_session_id', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['student_id'], ['student.id']),
        sa.ForeignKeyConstraint(['competition_id'], ['competitions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['test_session_id'], ['test_sessions.id'], ondelete='SET NULL')
    )
    
    # Índices para performance
    op.create_index('idx_coin_transactions_student_id', 'coin_transactions', ['student_id'])
    op.create_index('idx_coin_transactions_created_at', 'coin_transactions', ['created_at'])
```

### 1.2 Models

**Arquivo**: `app/models/studentCoins.py`

```python
from app import db
import uuid
from datetime import datetime

class StudentCoins(db.Model):
    __tablename__ = 'student_coins'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), 
                          onupdate=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    student = db.relationship('Student', backref='coins')
    
    def __repr__(self):
        return f'<StudentCoins student_id={self.student_id} balance={self.balance}>'
```

**Arquivo**: `app/models/coinTransaction.py`

```python
from app import db
import uuid
from datetime import datetime

class CoinTransaction(db.Model):
    __tablename__ = 'coin_transactions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_before = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String, nullable=False)
    competition_id = db.Column(db.String, db.ForeignKey('competitions.id', ondelete='SET NULL'))
    test_session_id = db.Column(db.String, db.ForeignKey('test_sessions.id', ondelete='SET NULL'))
    description = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    student = db.relationship('Student', backref='coin_transactions')
    competition = db.relationship('Competition', backref='coin_transactions')
    test_session = db.relationship('TestSession', backref='coin_transactions')
    
    def __repr__(self):
        return f'<CoinTransaction student_id={self.student_id} amount={self.amount}>'
```

### 1.3 Services

**Arquivo**: `app/services/coin_service.py`

```python
from app import db
from app.models.studentCoins import StudentCoins
from app.models.coinTransaction import CoinTransaction
from sqlalchemy.exc import IntegrityError

class InsufficientBalanceError(Exception):
    """Erro lançado quando saldo é insuficiente"""
    pass

class CoinService:
    @staticmethod
    def get_balance(student_id: str) -> int:
        """
        Retorna saldo de moedas do aluno
        Retorna 0 se aluno não tem registro ainda
        """
        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        return coins.balance if coins else 0
    
    @staticmethod
    def credit_coins(student_id: str, amount: int, reason: str, **kwargs) -> CoinTransaction:
        """
        Credita moedas para o aluno
        
        Args:
            student_id: ID do aluno
            amount: Quantidade de moedas (deve ser positivo)
            reason: Motivo (competition_participation, competition_rank_1, etc.)
            **kwargs: Campos opcionais (competition_id, test_session_id, description)
        
        Returns:
            CoinTransaction criada
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # Buscar ou criar StudentCoins
        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        if not coins:
            coins = StudentCoins(student_id=student_id, balance=0)
            db.session.add(coins)
        
        balance_before = coins.balance
        coins.balance += amount
        balance_after = coins.balance
        
        # Criar transação
        transaction = CoinTransaction(
            student_id=student_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            reason=reason,
            competition_id=kwargs.get('competition_id'),
            test_session_id=kwargs.get('test_session_id'),
            description=kwargs.get('description')
        )
        db.session.add(transaction)
        db.session.commit()
        
        return transaction
    
    @staticmethod
    def debit_coins(student_id: str, amount: int, reason: str, **kwargs) -> CoinTransaction:
        """
        Debita moedas do aluno (para loja futura)
        
        Raises:
            InsufficientBalanceError: Se saldo insuficiente
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        coins = StudentCoins.query.filter_by(student_id=student_id).first()
        if not coins or coins.balance < amount:
            raise InsufficientBalanceError(
                f"Saldo insuficiente. Disponível: {coins.balance if coins else 0}, Requerido: {amount}"
            )
        
        balance_before = coins.balance
        coins.balance -= amount
        balance_after = coins.balance
        
        transaction = CoinTransaction(
            student_id=student_id,
            amount=-amount,  # negativo para débito
            balance_before=balance_before,
            balance_after=balance_after,
            reason=reason,
            **kwargs
        )
        db.session.add(transaction)
        db.session.commit()
        
        return transaction
    
    @staticmethod
    def get_transaction_history(student_id: str, limit: int = 50, offset: int = 0):
        """
        Lista histórico de transações do aluno
        
        Returns:
            Lista de CoinTransaction (mais recentes primeiro)
        """
        return CoinTransaction.query.filter_by(student_id=student_id)\
            .order_by(CoinTransaction.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
```

### 1.4 Routes

**Arquivo**: `app/routes/coin_routes.py`

```python
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.coin_service import CoinService, InsufficientBalanceError
from app.decorators.role_required import role_required

bp = Blueprint('coins', __name__, url_prefix='/coins')

@bp.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """
    Retorna saldo do aluno logado
    Query params: ?student_id=xxx (admin/professor pode consultar qualquer aluno)
    """
    current_user = get_jwt_identity()
    
    # Admin/professor pode consultar qualquer aluno
    student_id = request.args.get('student_id')
    if student_id and current_user.role in ['admin', 'professor', 'coordenador']:
        target_student_id = student_id
    else:
        # Aluno só pode consultar próprio saldo
        target_student_id = current_user.student_id
    
    balance = CoinService.get_balance(target_student_id)
    
    return jsonify({
        'balance': balance,
        'student_id': target_student_id
    }), 200

@bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """
    Lista histórico de transações
    Query params: ?student_id=xxx, ?limit=50, ?offset=0
    """
    current_user = get_jwt_identity()
    
    student_id = request.args.get('student_id')
    if student_id and current_user.role in ['admin', 'professor', 'coordenador']:
        target_student_id = student_id
    else:
        target_student_id = current_user.student_id
    
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    
    transactions = CoinService.get_transaction_history(target_student_id, limit, offset)
    
    return jsonify({
        'transactions': [
            {
                'id': t.id,
                'amount': t.amount,
                'reason': t.reason,
                'description': t.description,
                'balance_after': t.balance_after,
                'created_at': t.created_at.isoformat(),
                'competition_id': t.competition_id,
                'test_session_id': t.test_session_id
            }
            for t in transactions
        ],
        'limit': limit,
        'offset': offset
    }), 200

@bp.route('/transactions/<string:transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """Detalhes de uma transação específica"""
    current_user = get_jwt_identity()
    
    transaction = CoinTransaction.query.get_or_404(transaction_id)
    
    # Verificar permissão
    if current_user.role == 'aluno' and transaction.student_id != current_user.student_id:
        return jsonify({'error': 'Forbidden'}), 403
    
    return jsonify({
        'id': transaction.id,
        'amount': transaction.amount,
        'balance_before': transaction.balance_before,
        'balance_after': transaction.balance_after,
        'reason': transaction.reason,
        'description': transaction.description,
        'created_at': transaction.created_at.isoformat(),
        'competition_id': transaction.competition_id,
        'test_session_id': transaction.test_session_id
    }), 200

@bp.route('/admin/credit', methods=['POST'])
@jwt_required()
@role_required('admin', 'coordenador')
def admin_credit_coins():
    """
    Credita moedas manualmente (admin apenas)
    Body: { student_id, amount, reason, description }
    """
    data = request.get_json()
    
    try:
        transaction = CoinService.credit_coins(
            student_id=data['student_id'],
            amount=data['amount'],
            reason=data.get('reason', 'admin_credit'),
            description=data.get('description')
        )
        
        return jsonify({
            'message': 'Moedas creditadas com sucesso',
            'transaction_id': transaction.id,
            'new_balance': transaction.balance_after
        }), 201
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Erro ao creditar moedas', 'details': str(e)}), 500
```

---

## Etapa 2: Competições CRUD

### Objetivo
Criar a estrutura de competições: tabelas, modelos, endpoints CRUD. Ainda sem inscrição de aluno ou aplicação de prova.

### 2.1 Migrations

**Arquivo**: `migrations/versions/add_competitions_table.py`

```python
def upgrade():
    op.create_table('competitions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('test_id', sa.String(), sa.ForeignKey('test.id')),
        sa.Column('subject_id', sa.String(), sa.ForeignKey('subject.id'), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('scope', sa.String(), default='individual'),
        sa.Column('scope_filter', sa.JSON()),
        sa.Column('enrollment_start', sa.TIMESTAMP(), nullable=False),
        sa.Column('enrollment_end', sa.TIMESTAMP(), nullable=False),
        sa.Column('application', sa.TIMESTAMP(), nullable=False),
        sa.Column('expiration', sa.TIMESTAMP(), nullable=False),
        sa.Column('timezone', sa.String(), default='America/Sao_Paulo'),
        sa.Column('question_mode', sa.String(), default='auto_random'),
        sa.Column('question_rules', sa.JSON()),
        sa.Column('reward_config', sa.JSON(), nullable=False),
        sa.Column('ranking_criteria', sa.String(), default='nota'),
        sa.Column('ranking_tiebreaker', sa.String(), default='tempo_entrega'),
        sa.Column('ranking_visibility', sa.String(), default='final'),
        sa.Column('max_participants', sa.Integer()),
        sa.Column('recurrence', sa.String(), default='manual'),
        sa.Column('template_id', sa.String(), sa.ForeignKey('competition_templates.id')),
        sa.Column('status', sa.String(), default='rascunho'),
        sa.Column('created_by', sa.String(), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Índices
    op.create_index('idx_competitions_status', 'competitions', ['status'])
    op.create_index('idx_competitions_level', 'competitions', ['level'])
    op.create_index('idx_competitions_subject_id', 'competitions', ['subject_id'])
```

### 2.2 Models

**Arquivo**: `app/models/competition.py`

```python
from app import db
import uuid
from datetime import datetime

class Competition(db.Model):
    __tablename__ = 'competitions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    test_id = db.Column(db.String, db.ForeignKey('test.id'))
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    scope = db.Column(db.String, default='individual')
    scope_filter = db.Column(db.JSON)
    enrollment_start = db.Column(db.TIMESTAMP, nullable=False)
    enrollment_end = db.Column(db.TIMESTAMP, nullable=False)
    application = db.Column(db.TIMESTAMP, nullable=False)
    expiration = db.Column(db.TIMESTAMP, nullable=False)
    timezone = db.Column(db.String, default='America/Sao_Paulo')
    question_mode = db.Column(db.String, default='auto_random')
    question_rules = db.Column(db.JSON)
    reward_config = db.Column(db.JSON, nullable=False)
    ranking_criteria = db.Column(db.String, default='nota')
    ranking_tiebreaker = db.Column(db.String, default='tempo_entrega')
    ranking_visibility = db.Column(db.String, default='final')
    max_participants = db.Column(db.Integer)
    recurrence = db.Column(db.String, default='manual')
    template_id = db.Column(db.String, db.ForeignKey('competition_templates.id'))
    status = db.Column(db.String, default='rascunho')
    created_by = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'),
                          onupdate=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    test = db.relationship('Test', backref='competitions')
    subject = db.relationship('Subject', backref='competitions')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_competitions')
    template = db.relationship('CompetitionTemplate', backref='competitions')
    
    @property
    def is_enrollment_open(self) -> bool:
        """Verifica se está no período de inscrição"""
        now = datetime.utcnow()
        return self.enrollment_start <= now <= self.enrollment_end
    
    @property
    def is_application_open(self) -> bool:
        """Verifica se está no período de aplicação"""
        now = datetime.utcnow()
        return self.application <= now <= self.expiration
    
    @property
    def is_finished(self) -> bool:
        """Verifica se já expirou"""
        now = datetime.utcnow()
        return now > self.expiration
    
    @property
    def enrolled_count(self) -> int:
        """Conta quantos alunos inscritos"""
        from app.models.studentTestOlimpics import StudentTestOlimpics
        return StudentTestOlimpics.query.filter_by(test_id=self.test_id).count()
    
    @property
    def available_slots(self) -> int:
        """Vagas disponíveis (None se ilimitado)"""
        if self.max_participants is None:
            return None
        return max(0, self.max_participants - self.enrolled_count)
```

### 2.3 Services

**Arquivo**: `app/services/competition_service.py`

```python
from app import db
from app.models.competition import Competition
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.studentTestOlimpics import StudentTestOlimpics
from datetime import datetime
import random

class ValidationError(Exception):
    """Erro de validação"""
    pass

class CompetitionService:
    @staticmethod
    def create_competition(data: dict, created_by_user_id: str) -> Competition:
        """
        Cria competição
        Se question_mode = 'auto_random': sorteia questões e cria Test
        Se question_mode = 'manual': deixa test_id = None (adicionar depois)
        """
        # Validar datas
        if data['enrollment_end'] > data['application']:
            raise ValidationError("Data de aplicação deve ser após fim da inscrição")
        
        competition = Competition(
            name=data['name'],
            description=data.get('description'),
            subject_id=data['subject_id'],
            level=data['level'],
            scope=data.get('scope', 'individual'),
            scope_filter=data.get('scope_filter'),
            enrollment_start=data['enrollment_start'],
            enrollment_end=data['enrollment_end'],
            application=data['application'],
            expiration=data['expiration'],
            timezone=data.get('timezone', 'America/Sao_Paulo'),
            question_mode=data.get('question_mode', 'auto_random'),
            question_rules=data.get('question_rules'),
            reward_config=data['reward_config'],
            ranking_criteria=data.get('ranking_criteria', 'nota'),
            ranking_tiebreaker=data.get('ranking_tiebreaker', 'tempo_entrega'),
            ranking_visibility=data.get('ranking_visibility', 'final'),
            max_participants=data.get('max_participants'),
            recurrence=data.get('recurrence', 'manual'),
            created_by=created_by_user_id,
            status='rascunho'
        )
        
        db.session.add(competition)
        db.session.flush()  # Para obter ID
        
        # Se auto_random, criar test e questões
        if competition.question_mode == 'auto_random':
            CompetitionService._create_test_with_random_questions(competition)
        
        db.session.commit()
        return competition
    
    @staticmethod
    def _create_test_with_random_questions(competition: Competition):
        """
        Sorteia questões baseado em question_rules e cria Test
        """
        rules = competition.question_rules
        num_questions = rules.get('num_questions', 10)
        
        # Query para buscar questões
        query = Question.query.filter_by(subject_id=competition.subject_id)
        
        if 'grade_ids' in rules:
            query = query.filter(Question.grade_level.in_(rules['grade_ids']))
        
        if 'difficulty_level' in rules and rules['difficulty_level']:
            query = query.filter_by(difficulty_level=rules['difficulty_level'])
        
        # Buscar questões disponíveis
        available_questions = query.all()
        
        if len(available_questions) < num_questions:
            raise ValidationError(
                f"Questões insuficientes. Disponíveis: {len(available_questions)}, Necessárias: {num_questions}"
            )
        
        # Sortear
        selected_questions = random.sample(available_questions, num_questions)
        
        # Criar Test
        test = Test(
            title=f"Prova - {competition.name}",
            description=competition.description,
            subject=competition.subject_id,
            evaluation_mode='virtual',
            created_by=competition.created_by
        )
        db.session.add(test)
        db.session.flush()
        
        # Criar test_questions
        for idx, question in enumerate(selected_questions, start=1):
            test_question = TestQuestion(
                test_id=test.id,
                question_id=question.id,
                order=idx
            )
            db.session.add(test_question)
        
        # Atualizar competition
        competition.test_id = test.id
    
    @staticmethod
    def add_questions_manually(competition_id: str, question_ids: list):
        """Adiciona questões manualmente (para question_mode = 'manual')"""
        competition = Competition.query.get_or_404(competition_id)
        
        if competition.question_mode != 'manual':
            raise ValidationError("Competição não está em modo manual")
        
        # Criar Test
        test = Test(
            title=f"Prova - {competition.name}",
            description=competition.description,
            subject=competition.subject_id,
            created_by=competition.created_by
        )
        db.session.add(test)
        db.session.flush()
        
        # Adicionar questões
        for idx, question_id in enumerate(question_ids, start=1):
            test_question = TestQuestion(
                test_id=test.id,
                question_id=question_id,
                order=idx
            )
            db.session.add(test_question)
        
        competition.test_id = test.id
        db.session.commit()
    
    @staticmethod
    def publish_competition(competition_id: str):
        """Publica competição (rascunho → aberta)"""
        competition = Competition.query.get_or_404(competition_id)
        
        # Validações
        if not competition.test_id:
            raise ValidationError("Test não foi criado ainda")
        
        if competition.enrollment_end > competition.application:
            raise ValidationError("Datas inválidas")
        
        if not competition.reward_config:
            raise ValidationError("Configuração de recompensas ausente")
        
        competition.status = 'aberta'
        db.session.commit()
    
    @staticmethod
    def cancel_competition(competition_id: str, reason: str = None):
        """Cancela competição"""
        competition = Competition.query.get_or_404(competition_id)
        competition.status = 'cancelada'
        db.session.commit()
        
        # TODO: notificar inscritos
```

---

## Checklist Final - Backend

### Etapa 1: Sistema de Moedas
- [ ] Migrations e Models
- [ ] Implementar CoinService
- [ ] Implementar routes

### Etapa 2: Competições CRUD
- [ ] Migration e Model
- [ ] Implementar CompetitionService
- [ ] Implementar routes CRUD

### Etapa 3: Inscrição
- [ ] Implementar lógica de filtros e inscrição

### Etapa 4: Aplicação e Entrega
- [ ] Implementar pagamento de participação

### Etapa 5: Ranking
- [ ] Implementar service e job de ranking

### Etapa 6: Templates
- [ ] Implementar templates e job

### Etapa 7: Avançadas
- [ ] Implementar websocket e funcionalidades avançadas
