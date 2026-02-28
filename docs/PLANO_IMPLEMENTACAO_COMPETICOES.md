# Plano de Implementação - Sistema de Competições

**Este documento foi dividido em dois planos separados para melhor organização:**

- **📘 Backend**: [PLANO_IMPLEMENTACAO_BACKEND.md](./PLANO_IMPLEMENTACAO_BACKEND.md)
- **📗 Frontend**: [PLANO_IMPLEMENTACAO_FRONTEND.md](./PLANO_IMPLEMENTACAO_FRONTEND.md)

---

## Visão Geral Consolidada

Este documento consolida a visão geral do projeto. Para detalhes de implementação, consulte os planos específicos de backend e frontend.

---

## Visão geral das etapas

| Etapa | Descrição                                    | Dependências |
| ----- | ---------------------------------------------- | ------------- |
| 1     | Sistema de Moedas (base)                       | Nenhuma       |
| 2     | Competições CRUD (estrutura básica)         | Etapa 1       |
| 3     | Inscrição e Listagem                         | Etapa 2       |
| 4     | Aplicação e Entrega (integração com prova) | Etapa 3       |
| 5     | Ranking e Pagamento de Recompensas             | Etapa 4       |
| 6     | Templates e Criação Automática              | Etapa 5       |
| 7     | Funcionalidades Avançadas                     | Etapa 6       |

---

## Modelo de Dados e Decisões de Desenho

Este bloco consolida as decisões de tabelas, reuso de cálculos e comportamento do ranking.

### Tabelas do sistema de competições

**Todas as tabelas de competições são criadas o quanto antes (Etapa 2)** numa única migration (ou em sequência na mesma etapa), para não precisar criar tabelas ou adicionar campos em etapas futuras. Nas etapas seguintes apenas se implementa a lógica que usa essas tabelas.

| Tabela                                | Criar em                   | Descrição                                                                                                                                                                                                         |
| ------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **competitions**                | Etapa 2                    | Metadados da competição, datas, reward_config, test_id (prova vinculada), etc.                                                                                                                                    |
| **competition_templates**       | Etapa 2 (ou já existente) | Templates para criar competições recorrentes (Etapa 6 usa; tabela já existe).                                                                                                                                    |
| **competition_enrollments**     | Etapa 2                    | Inscrições: competition_id, student_id, enrolled_at, status. Etapa 3 só implementa a lógica de inscrição.                                                                                                     |
| **competition_results**         | Etapa 2                    | Snapshot dos resultados (preenchido só ao finalizar a competição). Campos: posição, nota, proficiência, média, acertos, tempo, moedas_ganhas, etc. Etapa 5 só implementa a lógica de gravação e leitura. |
| **competition_ranking_payouts** | Etapa 2 (opcional)         | Auditoria de pagamentos de ranking (competition_id, student_id, position, amount, paid_at). Etapa 5 usa.                                                                                                            |
| **competition_rewards**         | Etapa 2                    | Controle de pagamento de moedas de participação (competition_id, student_id, participation_paid_at). Etapa 4 só implementa a lógica ao finalizar prova.                                                         |

**O que não temos**

- **competition_questions**: as questões da prova ficam em `test` + `test_questions` (prova é um `Test` normal). Não existe tabela própria de “questões da competição”.

### Competições por schema (public vs município)

O sistema é multi-tenant por município: existem o schema **public** e schemas **city_&lt;city_id&gt;** (um por município). Cada competição é gravada em **um único** schema (não há réplica em "ambos").

| Escopo | Onde a competição é gravada |
|--------|-----------------------------|
| `individual`, `estado`, `global` | **public** |
| `municipio` (um único city_id em scope_filter) | Schema **city_&lt;id&gt;** desse município |
| `municipio` (vários city_ids) | **public** (visibilidade por scope na leitura) |
| `escola` (escolas de uma única cidade) | Schema **city_&lt;id&gt;** da cidade das escolas |
| `escola` (escolas de cidades diferentes) | **public** |
| `turma` (turmas de uma única cidade) | Schema **city_&lt;id&gt;** da cidade das turmas |
| `turma` (turmas de cidades diferentes) | **public** |

- **Listagem**: as APIs de listagem unem competições de **public** e do schema do tenant (quando o request tem contexto de cidade), para que o usuário veja tanto competições globais quanto do seu município.
- **Criação**: ao criar competição, o backend determina o schema alvo com base em `scope` e `scope_filter` e grava nesse schema.
- **Re-upload / import**: ao subir competições novamente (ex.: após apagar do banco), usar a mesma regra: competições individual/estado/global em **public**; municipio (1 cidade)/escola/turma no schema do município correspondente.

### Reuso dos resultados da avaliação

- **Cálculos de nota, proficiência, média, etc.** continuam sendo feitos **somente** nas tabelas e serviços já existentes de resultado da avaliação (ex.: sessões de prova, tabelas de resultado por questão/habilidade).
- A tabela **competition_results** não recalcula nada: ela armazena uma **cópia** dos valores já calculados (proficiência, média, nota, acertos, tempo, etc.) no momento do fechamento da competição.
- Assim, proficiência e média na competição são **as mesmas** da avaliação; apenas são gravadas em `competition_results` para histórico e ranking oficial.

### Ranking: posição só ao finalizar (Opção 1)

- **Durante a competição** (status aberta / em andamento):
  - **Ranking “ao vivo”**: calculado **em tempo real** a partir dos resultados da avaliação (ex.: sessões finalizadas do `test_id` da competição). **Nenhuma** posição é gravada em `competition_results` nessa fase.
  - O endpoint de ranking (ex.: `GET /competitions/:id/ranking`) usa as mesmas fontes de dados da avaliação e aplica o critério de ordenação (nota, tempo, etc.).
- **Quando a competição é finalizada** (status → encerrada):
  - Um job (ou ação de “encerrar competição”) executa **uma vez**:
    1. Calcula o ranking a partir dos resultados da avaliação.
    2. Grava em **competition_results** um registro por participante com: posição, nota, proficiência, média, acertos, tempo, moedas_ganhas, etc. (todos copiados das tabelas de resultado da avaliação).
    3. Distribui moedas de ranking (CoinService) conforme reward_config.
  - A partir daí, o ranking “oficial” pode ser lido de `competition_results` (opcional; também pode continuar sendo calculado a partir dos mesmos dados, com o mesmo resultado).

Resumo: **posição e demais campos em `competition_results` são atualizados no banco apenas após o status da competição ser finalizado**; durante a prova, o ranking é apenas calculado e exibido em tempo real, sem escrever posição em tabela.

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

---

## Etapa 2: Competições CRUD (estrutura básica)

### Objetivo

Criar a estrutura de competições: tabelas, modelos, endpoints CRUD e página de gerenciamento (admin/coordenador). Ainda sem inscrição de aluno ou aplicação de prova.

### Backend

#### 2.1 Migrations

**Arquivo**: `migrations/versions/add_competitions_tables.py` (ou único arquivo com todas as tabelas de competições)

Criar **todas** as tabelas de competições nesta etapa para não precisar de novas migrations nas etapas 3, 4 e 5. Ordem de criação (respeitando FKs): `competition_templates` (se ainda não existir) → `competitions` → `competition_enrollments` → `competition_rewards` → `competition_results` → `competition_ranking_payouts`.

```python
# ---- Tabela: competition_templates (se ainda não existir) ----
# (campos conforme já definido no projeto)

# ---- Tabela: competitions ----
- id (String/UUID, PK)
- name (String, required)
- description (Text)
- test_id (String, FK → test.id, nullable)
- subject_id (String, FK → subject.id)
- level (Integer)
- scope (String, default='individual')
- scope_filter (JSON, nullable)
- enrollment_start (TIMESTAMP)
- enrollment_end (TIMESTAMP)
- application (TIMESTAMP)
- expiration (TIMESTAMP)
- timezone (String, default='America/Sao_Paulo')
- question_mode (String, default='auto_random')
- question_rules (JSON, nullable)
- reward_config (JSON, required)
- ranking_criteria (String, default='nota')
- ranking_tiebreaker (String, default='tempo_entrega')
- ranking_visibility (String, default='final')
- max_participants (Integer, nullable)
- recurrence (String, default='manual')
- template_id (String, FK → competition_templates.id, nullable)
- status (String, default='rascunho')
- created_by (String, FK → users.id)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

# ---- Tabela: competition_enrollments (criar já na Etapa 2) ----
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id, ondelete=CASCADE)
- student_id (String, FK → student.id, ondelete=CASCADE)
- enrolled_at (TIMESTAMP, server_default=CURRENT_TIMESTAMP)
- status (String, default='inscrito')  # inscrito, cancelado
# Constraint: unique(competition_id, student_id)
# Índices: competition_id, student_id, status

# ---- Tabela: competition_rewards (criar já na Etapa 2) ----
# Controle de pagamento de moedas de participação (usado na Etapa 4)
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id, ondelete=CASCADE)
- student_id (String, FK → student.id, ondelete=CASCADE)
- participation_paid_at (TIMESTAMP, nullable)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
# Constraint: unique(competition_id, student_id)
# Índices: competition_id, student_id

# ---- Tabela: competition_results (criar já na Etapa 2) ----
# Preenchida apenas quando a competição é finalizada (snapshot dos resultados da avaliação)
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id, ondelete=CASCADE)
- student_id (String, FK → student.id, ondelete=CASCADE)
- session_id (String, FK → test_sessions.id, ondelete=CASCADE)
- correct_answers (Integer)
- total_questions (Integer)
- score_percentage (Float)
- grade (Float)
- proficiency (Float, nullable)
- classification (String, nullable)
- posicao (Integer)
- moedas_ganhas (Integer, default=0)
- tempo_gasto (Integer, nullable)
- acertos (Integer)
- erros (Integer)
- em_branco (Integer)
- calculated_at (TIMESTAMP)
# Constraint: unique(competition_id, student_id) ou (competition_id, session_id)
# Índices: competition_id, student_id, posicao

# ---- Tabela: competition_ranking_payouts (opcional, auditoria; criar já na Etapa 2) ----
- id (String/UUID, PK)
- competition_id (String, FK → competitions.id)
- student_id (String, FK → student.id)
- position (Integer)
- amount (Integer)
- paid_at (TIMESTAMP)
- created_at (TIMESTAMP)
# Constraint: unique(competition_id, student_id)
```

#### 2.2 Models

Criar os models de **todas** as tabelas de competições nesta etapa, para que as etapas 3 e 5 só implementem lógica e rotas.

**Arquivo**: `app/models/competition.py` (ou `app/competitions/models/competition.py`)

```python
class Competition(db.Model):
    # Campos conforme migration (competitions)
    # Relacionamentos: test, subject, creator, template
    # Propriedades: is_enrollment_open, is_application_open, is_finished, enrolled_count, available_slots
```

**Arquivo**: `app/competitions/models/competition_enrollment.py` (ou equivalente)

```python
class CompetitionEnrollment(db.Model):
    __tablename__ = 'competition_enrollments'
    # id, competition_id, student_id, enrolled_at, status
    # Relacionamentos: competition, student
```

**Arquivo**: `app/competitions/models/competition_result.py` (ou equivalente)

```python
class CompetitionResult(db.Model):
    __tablename__ = 'competition_results'
    # id, competition_id, student_id, session_id, correct_answers, total_questions,
    # score_percentage, grade, proficiency, classification, posicao, moedas_ganhas,
    # tempo_gasto, acertos, erros, em_branco, calculated_at
    # Relacionamentos: competition, student, test_session
```

**Arquivo**: `app/competitions/models/competition_reward.py` (ou equivalente)

```python
class CompetitionReward(db.Model):
    __tablename__ = 'competition_rewards'
    # id, competition_id, student_id, participation_paid_at, created_at, updated_at
    # Relacionamentos: competition, student
```

**Arquivo** (opcional): `app/competitions/models/competition_ranking_payout.py`

```python
class CompetitionRankingPayout(db.Model):
    __tablename__ = 'competition_ranking_payouts'
    # id, competition_id, student_id, position, amount, paid_at, created_at
    # Relacionamentos: competition, student
```

Assim, **enrolled_count** em Competition pode ser implementado contando `CompetitionEnrollment.query.filter_by(competition_id=self.id, status='inscrito').count()` (se usar competition_enrollments) ou mantendo a contagem via student_test_olimpics, conforme decisão do projeto.

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
- Escopo (select: Individual, Turma, Escola, Município, Estado) — valores da API: `individual`, `turma`, `escola`, `municipio`, `estado` (não há mais escopo "série").
  - **Individual:** nenhum filtro; enviar `scope_filter: {}`.
  - **Turma:** multi-select de turmas **do nível selecionado** na competição. Chamar `GET /competitions/eligible-classes?level=1` ou `level=2` (conforme o nível da competição); só aparecem turmas cuja série pertence a esse nível. Enviar `scope_filter: { "class_ids": ["uuid", ...] }`.
  - **Escola:** filtro em cascata: **Estado** → **Município** → escolas. 1) Listar estados: `GET /city/states`. 2) Listar municípios do estado: `GET /city/municipalities/state/<state_name>`. 3) Listar escolas do município: `GET /schools?city_id=<city_id>`. Enviar `scope_filter: { "school_ids": ["uuid", ...] }`.
  - **Município:** filtro por **Estado** primeiro. 1) Listar estados: `GET /city/states`. 2) Listar municípios: `GET /city/municipalities/state/<state_name>`. Enviar `scope_filter: { "city_ids": ["uuid", ...] }` ou `"municipality_ids"`.
  - **Estado:** sem filtro; listar estados com `GET /city/states` e multi-select. Enviar `scope_filter: { "state_names": ["SP", "RJ", ...] }` ou `"state"`.
  - Para escopos não-individual, o backend exige ao menos um item no filtro correspondente.
  - **Quem pode usar cada escopo** depende do seu perfil (veja abaixo). O frontend deve chamar `GET /competitions/allowed-scopes` e exibir no select apenas os escopos retornados.

**Permissões de escopo por perfil (role)** — instruções simples

Quem cria a competição tem um **perfil** (administrador, tec adm, diretor, coordenador ou professor). Cada perfil só pode escolher certos tipos de escopo. O sistema bloqueia o que não for permitido.

- **Administrador**
  - Pode usar **todos** os escopos: Individual, Turma, Escola, Município, Estado.
  - O escopo **Individual** para o admin significa “competição aberta para todo o sistema” (qualquer aluno que atenda ao nível pode participar). Funciona como “geral”.

- **Tec adm (administrador técnico do município)**
  - Pode usar apenas o que for **do seu município**:
    - **Individual** (quem estiver no seu município, conforme regras do sistema).
    - **Município**: só o **seu** município (não pode escolher outro).
    - **Escola**: só escolas que pertencem ao seu município.
    - **Turma**: só turmas de escolas do seu município (e do nível da competição).
  - **Não** pode usar escopo por Estado (vários municípios).

- **Diretor e Coordenador**
  - Pode usar apenas o que for **da sua escola**:
    - **Individual** (no âmbito da sua escola, conforme regras do sistema).
    - **Escola**: só **a sua** escola (não pode escolher outra).
    - **Turma**: só turmas da sua escola (e do nível da competição).
  - **Não** pode usar escopo por Município nem por Estado.

- **Professor**
  - Pode usar apenas:
    - **Individual** (no âmbito em que o sistema permitir).
    - **Turma**: só turmas **em que você dá aula** (vinculadas a você), do nível da competição. Não pode escolher turmas de outros professores.
  - **Não** pode usar escopo por Escola, Município ou Estado.

Resumo para o frontend: chamar `GET /competitions/allowed-scopes` ao abrir o formulário de criação/edição e montar o select de “Escopo” apenas com os valores retornados em `allowed_scopes`. Ao salvar, o backend valida de novo; se o usuário tiver alterado algo e estiver fora do permitido, retorna erro 400 com mensagem clara.

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

## Etapa 3: Inscrição e Listagem (Aluno)

### Objetivo

Permitir que alunos vejam competições disponíveis e se inscrevam. Integrar com o fluxo de prova (ex.: `student_test_olimpics`) para liberar a prova.

### Backend

**Tabelas**: A tabela `competition_enrollments` já foi criada na Etapa 2. Nesta etapa implementar apenas os models (se ainda não tiverem sido criados), serviços e rotas que usam essa tabela.

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
# Ação: cria registro em competition_enrollments (se a tabela existir) e em student_test_olimpics (test_id da competição, application, expiration)
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
    # Se existir tabela competition_enrollments: criar registro (competition_id, student_id, status='inscrito')
    # Criar (ou garantir) StudentTestOlimpics para liberar a prova:
    #   - student_id, test_id = competition.test_id
    #   - application, expiration, timezone da competição
    # Retorna: sucesso ou erro

@staticmethod
def unenroll_student(competition_id, student_id):
    # Valida: antes do período de aplicação
    # Se existir competition_enrollments: atualizar status para 'cancelado' ou remover registro
    # Remover StudentTestOlimpics (student_id, test_id da competição)
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

## Etapa 4: Aplicação e Entrega (integração com prova)

### Objetivo

Integrar competições com o fluxo de prova existente: aluno acessa prova pela competição, faz e entrega. Ao entregar, concede moedas de participação.

### Backend

**Tabelas**: A tabela `competition_rewards` já foi criada na Etapa 2. Nesta etapa implementar apenas a lógica que verifica/marca participação paga e credita moedas (CoinService).

#### 4.1 Services (modificar existente)

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

#### 4.2 Routes (adicionar em `competition_routes.py`)

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

## Etapa 5: Ranking e Pagamento de Recompensas

### Objetivo

Calcular ranking ao fim da competição, gravar snapshot em `competition_results` (proficiência, média, posição, etc. copiados dos resultados da avaliação), pagar moedas para as posições premiadas e exibir ranking para alunos. Durante a competição, o ranking é calculado em tempo real a partir dos resultados da avaliação, sem escrever em `competition_results`.

### Backend

**Tabelas**: As tabelas `competition_results` e `competition_ranking_payouts` já foram criadas na Etapa 2. Nesta etapa implementar apenas os models (CompetitionResult, CompetitionRankingPayout, se ainda não tiverem sido criados), o serviço de ranking e o job de finalização que preenche e lê essas tabelas.

#### 5.1 Models (se ainda não criados na Etapa 2)

- **CompetitionResult**: model correspondente à tabela `competition_results` (relacionamentos com Competition, Student, TestSession).
- **CompetitionRankingPayout**: model correspondente à tabela `competition_ranking_payouts` (opcional, para auditoria).

#### 5.2 Services

**Arquivo**: `app/services/competition_ranking_service.py`

**Durante a competição** (status aberta / em andamento): ranking é calculado **em tempo real** a partir dos resultados da avaliação (test_sessions e tabelas de resultado existentes). Nada é escrito em `competition_results`.

**Ao finalizar a competição** (status → encerrada): um job ou ação única (1) calcula o ranking a partir dos mesmos dados da avaliação, (2) grava snapshot em `competition_results` (copiando proficiência, média, nota, acertos, tempo, etc. das tabelas de resultado), (3) paga moedas de ranking e opcionalmente registra em `competition_ranking_payouts`.

```python
class CompetitionRankingService:
    @staticmethod
    def calculate_ranking(competition_id):
        """
        Calcula ranking a partir dos resultados da avaliação (test_sessions / tabelas de resultado).
        Usado tanto para exibir ranking ao vivo quanto no passo de finalização.
        Retorna: lista ordenada de {student_id, session_id, value, position, grade, proficiency, ...}
        """
        competition = Competition.query.get(competition_id)
        # Buscar sessões finalizadas e dados já calculados (nota, proficiência, etc.)
        # da mesma forma que os resultados da avaliação são obtidos
        test_sessions = TestSession.query.filter_by(
            test_id=competition.test_id,
            status='finalizada'
        ).all()
    
        # Enriquecer com proficiência, média, etc. das tabelas de resultado da avaliação
        # (reutilizar serviços/queries já existentes)
    
        # Ordenar conforme ranking_criteria e ranking_tiebreaker
        if competition.ranking_criteria == 'nota':
            sorted_sessions = sorted(test_sessions, key=lambda s: s.grade or 0, reverse=True)
        elif competition.ranking_criteria == 'tempo':
            sorted_sessions = sorted(test_sessions, key=lambda s: s.duration_minutes or 999999)
        # ... outros critérios e tiebreaker
    
        ranking = []
        for idx, session in enumerate(sorted_sessions, start=1):
            ranking.append({
                'position': idx,
                'student_id': session.student_id,
                'session_id': session.id,
                'value': session.grade,  # ou tempo, acertos
                'grade': session.grade,
                'proficiency': ...,   # copiado das tabelas de resultado
                'correct_answers': ...,
                # ... demais campos para o snapshot
            })
        return ranking
  
    @staticmethod
    def finalize_competition_and_save_results(competition_id):
        """
        Chamado uma vez quando a competição é encerrada.
        1) Calcula ranking a partir dos resultados da avaliação.
        2) Grava snapshot em competition_results (copia proficiência, média, nota, etc.).
        3) Paga moedas de ranking (CoinService) e opcionalmente registra em competition_ranking_payouts.
        """
        competition = Competition.query.get_or_404(competition_id)
        ranking = CompetitionRankingService.calculate_ranking(competition_id)
    
        for item in ranking:
            # Criar registro em competition_results (snapshot)
            result = CompetitionResult(
                competition_id=competition_id,
                student_id=item['student_id'],
                session_id=item['session_id'],
                posicao=item['position'],
                correct_answers=item['correct_answers'],
                grade=item['grade'],
                proficiency=item.get('proficiency'),
                # ... copiar todos os campos das tabelas de resultado
                moedas_ganhas=0,  # preenchido abaixo se premiado
                calculated_at=datetime.utcnow(),
            )
            db.session.add(result)
    
        # Pagar moedas para posições premiadas
        CompetitionRankingService.pay_ranking_rewards(competition_id, ranking)
    
        # Atualizar moedas_ganhas em competition_results para cada premiado
        # ...
        db.session.commit()
  
    @staticmethod
    def pay_ranking_rewards(competition_id, ranking=None):
        """
        Credita moedas para posições premiadas (CoinService).
        Se existir competition_ranking_payouts, registra o pagamento.
        """
        competition = Competition.query.get(competition_id)
        if ranking is None:
            ranking = CompetitionRankingService.calculate_ranking(competition_id)
    
        ranking_rewards = competition.reward_config.get('ranking_rewards', [])
        for reward_config in ranking_rewards:
            position = reward_config['position']
            coins = reward_config['coins']
            if position <= len(ranking):
                student_id = ranking[position - 1]['student_id']
                # Creditar e opcionalmente registrar em competition_ranking_payouts
                CoinService.credit_coins(...)
  
    @staticmethod
    def get_ranking(competition_id, limit=100):
        """
        Se competição encerrada: pode ler de competition_results (ranking oficial).
        Se competição em andamento: calcula em tempo real (calculate_ranking) a partir dos resultados da avaliação.
        Retorna lista enriquecida com student_name, student_class, etc.
        """
        competition = Competition.query.get(competition_id)
        if competition.status == 'encerrada':
            # Ler de competition_results
            results = CompetitionResult.query.filter_by(competition_id=competition_id)\
                .order_by(CompetitionResult.posicao).limit(limit).all()
            return [enriquecer(item) for item in results]
        else:
            # Ranking ao vivo: calcular a partir da avaliação
            return CompetitionRankingService.calculate_ranking(competition_id)[:limit]
```

#### 5.3 Celery Task (Job)

**Arquivo**: `app/services/celery_tasks/competition_tasks.py`

```python
@celery.task
def process_finished_competitions():
    """
    Job que roda periodicamente (ex: a cada hora).
    Processa competições que expiraram e ainda não foram finalizadas.
    Ao finalizar: grava snapshot em competition_results (proficiência, média, posição, etc.)
    e paga moedas de ranking. Posição e competition_results só são atualizados neste momento.
    """
    now = datetime.utcnow()
  
    competitions = Competition.query.filter(
        Competition.expiration < now,
        Competition.status.in_(['aberta', 'em_andamento'])
    ).all()
  
    for competition in competitions:
        # Verificar se já foi finalizada (já tem registros em competition_results)
        has_results = CompetitionResult.query.filter_by(competition_id=competition.id).count() > 0
        if not has_results:
            # 1) Gravar snapshot em competition_results (copiar dados da avaliação)
            # 2) Pagar moedas de ranking
            CompetitionRankingService.finalize_competition_and_save_results(competition.id)
        
            competition.status = 'encerrada'
            db.session.commit()
        
            logger.info(f"Competição {competition.id} encerrada; results e ranking pagos")
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
# Durante a competição: ranking calculado em tempo real a partir dos resultados da avaliação (não lê competition_results)
# Após encerrar: ranking pode ser lido de competition_results (snapshot com posição, proficiência, média, etc.)
# Validações:
#   - Se ranking_visibility = 'realtime': retorna sempre (se houver sessões finalizadas)
#   - Se ranking_visibility = 'final': só retorna se competition.status = 'encerrada'
# Permissões: alunos inscritos, professor/admin
# Retorna: lista de {position, student_name, student_class, value, proficiency, ...}

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

---

## Resumo de Prioridades

### MVP (Mínimo Viável)

- Etapa 1: Sistema de Moedas
- Etapa 2: Competições CRUD
- Etapa 3: Inscrição e Listagem
- Etapa 4: Aplicação e Entrega
- Etapa 5: Ranking e Pagamento

**Com essas 5 etapas, o sistema já funciona end-to-end**: criar competição, aluno se inscrever, fazer prova, ganhar moedas, ver ranking.

- Etapa 6: Templates e Criação Automática
- Etapa 7: Funcionalidades Avançadas (ranking em tempo real, notificações, analytics)

---

## Checklist Final de Implementação

### Etapa 1: Sistema de Moedas

#### Backend

- [ ] Criar migrations (student_coins, coin_transactions)
- [ ] Implementar models (StudentCoins, CoinTransaction)
- [ ] Implementar CoinService
- [ ] Implementar routes (/coins/*)

#### Frontend

- [ ] Implementar CoinBalance component
- [ ] Implementar CoinHistory page
- [ ] Integrar no header/navbar

### Etapa 2: Competições CRUD

#### Backend

- [ ] Criar migration com todas as tabelas de competições (competitions, competition_enrollments, competition_rewards, competition_results, competition_ranking_payouts)
- [ ] Implementar models (Competition, CompetitionEnrollment, CompetitionReward, CompetitionResult, CompetitionRankingPayout)
- [ ] Implementar CompetitionService
- [ ] Implementar routes CRUD

#### Frontend

- [ ] Implementar CompetitionList (admin)
- [ ] Implementar CreateCompetitionModal
- [ ] Implementar CompetitionDetails

### Etapa 3: Inscrição e Listagem

#### Backend

- [ ] Implementar filtros de competições disponíveis
- [ ] Implementar enroll/unenroll endpoints

#### Frontend

- [ ] Implementar CompetitionListStudent
- [ ] Implementar EnrollConfirmationModal

### Etapa 4: Aplicação e Entrega

#### Backend

- [ ] Implementar lógica de pagamento na finalização (usar tabela competition_rewards já criada na Etapa 2)

#### Frontend

- [ ] Implementar botão "Fazer prova"
- [ ] Implementar CompetitionSubmitSuccessModal

### Etapa 5: Ranking e Pagamento

#### Backend

- [ ] Implementar CompetitionRankingService (usar tabelas já criadas na Etapa 2)
- [ ] Implementar Celery task
- [ ] Implementar routes de ranking

#### Frontend

- [ ] Implementar CompetitionRanking
- [ ] Implementar polling/websocket (realtime)

### Etapa 6: Templates

#### Backend

- [ ] Criar migration (competition_templates) se ainda não existir
- [ ] Implementar template CRUD
- [ ] Implementar Celery task (criação automática)

#### Frontend

- [ ] Implementar TemplateList
- [ ] Implementar CreateTemplateModal

### Etapa 7: Avançadas

#### Backend

- [ ] Implementar funcionalidades avançadas (websocket, notificações, performance)

#### Frontend

- [ ] Implementar features avançadas (realtime, analytics)

---

## Arquivos Separados

Para implementação detalhada, consulte os planos específicos:

### Backend - [PLANO_IMPLEMENTACAO_BACKEND.md](./PLANO_IMPLEMENTACAO_BACKEND.md)

- Migrations, models, services, routes, Celery tasks
- Checklist por etapa

### Frontend - [PLANO_IMPLEMENTACAO_FRONTEND.md](./PLANO_IMPLEMENTACAO_FRONTEND.md)

- Componentes, páginas, modais, rotas
- Checklist por etapa

---

## Roadmap de Implementação

### Fase 1: MVP (Etapas 1-5) - 4-6 semanas

- Sistema completo de competições funcional
- Alunos podem se inscrever e participar
- Moedas e ranking funcionando

### Fase 2: Automação (Etapa 6) - 2-3 semanas

- Templates e criação automática
- Competições recorrentes semanais/mensais

### Fase 3: Avançadas (Etapa 7) - 3-4 semanas

- Ranking em tempo real
- Notificações
- Analytics e relatórios
- Otimizações de performance

**Total estimado**: 9-13 semanas

---

## Links Rápidos

- [Plano Backend](./PLANO_IMPLEMENTACAO_BACKEND.md)
- [Plano Frontend](./PLANO_IMPLEMENTACAO_FRONTEND.md)
