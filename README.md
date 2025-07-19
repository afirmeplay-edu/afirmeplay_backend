# InnovaPlay Backend - Sistema de Avaliações

Sistema backend para gerenciamento de avaliações educacionais com cálculo automático de resultados, correção manual de questões dissertativas e relatórios detalhados de desempenho.

## 📋 Índice

- [Visão Geral](#visão-geral)
- [Funcionalidades Principais](#funcionalidades-principais)
- [Endpoints de Resultados](#endpoints-de-resultados)
- [Controle de Acesso](#controle-de-acesso)
- [Estrutura de Dados](#estrutura-de-dados)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)

## 🎯 Visão Geral

O InnovaPlay Backend é um sistema completo para gerenciamento de avaliações educacionais que oferece:

- **Criação e aplicação de avaliações** por professores
- **Cálculo automático de resultados** para questões objetivas
- **Correção manual** para questões dissertativas
- **Relatórios detalhados** de desempenho por aluno e turma
- **Análise de habilidades** e competências
- **Controle de acesso** baseado em papéis (professor, admin, coordenador, diretor)

## 🚀 Funcionalidades Principais

### ✅ Sistema de Avaliações
- Criação de avaliações com múltiplas disciplinas
- Aplicação de avaliações por turma com datas de início e expiração
- Questões de múltipla escolha e dissertativas
- Controle de tempo e disponibilidade

### ✅ Cálculo Automático de Resultados
- Correção automática de questões objetivas
- Cálculo de proficiência em escala 0-1000
- Classificação por níveis (Abaixo do Básico, Básico, Adequado, Avançado)
- Estatísticas por turma e escola

### ✅ Correção Manual
- Interface para correção de questões dissertativas
- Atribuição de pontuação manual
- Feedback personalizado por questão
- Controle de status de correção

### ✅ Relatórios e Analytics
- Relatórios detalhados por avaliação
- Análise de desempenho por habilidade
- Comparação entre turmas e escolas
- Exportação de dados

## 📊 Endpoints de Resultados

### 1. 📋 Listar Avaliações com Estatísticas
**`GET /evaluation-results/avaliacoes`**

Retorna todas as avaliações com estatísticas agregadas de desempenho.

**Query Parameters:**
- `page` (opcional): Número da página (padrão: 1)
- `per_page` (opcional): Itens por página (padrão: 20, máximo: 100)
- `status` (opcional): Filtrar por status (pendente, agendada, em_andamento, concluida)
- `subject_id` (opcional): Filtrar por disciplina
- `grade_id` (opcional): Filtrar por série

**Resposta:**
```json
{
  "data": [
    {
      "id": "test_id",
      "titulo": "Avaliação de Matemática - 9º Ano",
      "disciplina": "Matemática",
      "curso": "Ensino Fundamental",
      "serie": "9º Ano",
      "escola": "Escola ABC",
      "municipio": "São Paulo",
      "data_aplicacao": "2024-01-01T10:00:00",
      "data_correcao": "2024-01-02T15:30:00",
      "status": "concluida",
      "total_alunos": 25,
      "alunos_participantes": 23,
      "alunos_pendentes": 0,
      "alunos_ausentes": 2,
      "media_nota": 7.2,
      "media_proficiencia": 645.5,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 3,
        "basico": 8,
        "adequado": 10,
        "avancado": 2
      },
      "turmas_desempenho": []
    }
  ],
  "total": 15,
  "page": 1,
  "per_page": 20,
  "total_pages": 1
}
```

### 2. 📊 Resultados por Aluno
**`GET /evaluation-results/alunos?avaliacao_id={id}`**

Retorna resultados detalhados de todos os alunos de uma avaliação específica.

**Query Parameters:**
- `avaliacao_id` (obrigatório): ID da avaliação

**Resposta:**
```json
{
  "data": [
    {
      "id": "student_id",
      "nome": "João Silva",
      "turma": "9º A",
      "nota": 7.5,
      "proficiencia": 652.3,
      "classificacao": "Adequado",
      "questoes_respondidas": 18,
      "acertos": 15,
      "erros": 3,
      "em_branco": 2,
      "tempo_gasto": 3600,
      "status": "concluida"
    },
    {
      "id": "student_id_2",
      "nome": "Maria Santos",
      "turma": "9º A",
      "nota": 0.0,
      "proficiencia": 0.0,
      "classificacao": "Abaixo do Básico",
      "questoes_respondidas": 0,
      "acertos": 0,
      "erros": 0,
      "em_branco": 20,
      "tempo_gasto": 0,
      "status": "nao_respondida"
    }
  ]
}
```

### 3. 📈 Relatório Detalhado
**`GET /evaluation-results/relatorio-detalhado/{evaluation_id}`**

Relatório completo com questões, habilidades e respostas detalhadas de cada aluno.

**Resposta:**
```json
{
  "avaliacao": {
    "id": "test_id",
    "titulo": "Avaliação de Matemática - 9º Ano",
    "disciplina": "Matemática",
    "total_questoes": 20
  },
  "questoes": [
    {
      "id": "question_id",
      "numero": 1,
      "texto": "Questão sobre números e operações",
      "habilidade": "Números e Operações",
      "codigo_habilidade": "9N1.1",
      "tipo": "multipleChoice",
      "dificuldade": "Fácil",
      "porcentagem_acertos": 85.5,
      "porcentagem_erros": 14.5
    }
  ],
  "alunos": [
    {
      "id": "student_id",
      "nome": "João Silva",
      "turma": "9º A",
      "respostas": [
        {
          "questao_id": "q1",
          "questao_numero": 1,
          "resposta_correta": true,
          "resposta_em_branco": false,
          "tempo_gasto": 120
        }
      ],
      "total_acertos": 15,
      "total_erros": 3,
      "total_em_branco": 2,
      "nota_final": 7.5,
      "proficiencia": 652,
      "classificacao": "Adequado"
    }
  ]
}
```

### 4. 🎯 Resultados de Aluno Específico
**`GET /evaluation-results/{test_id}/student/{student_id}/results`**

Resultados detalhados de um aluno específico em uma avaliação.

**Query Parameters:**
- `include_answers` (opcional): "true" para incluir respostas detalhadas

**Resposta:**
```json
{
  "test_id": "test_id",
  "student_id": "student_id",
  "student_db_id": "student_db_id",
  "total_questions": 20,
  "answered_questions": 18,
  "correct_answers": 15,
  "score_percentage": 75.0,
  "total_score": 15.0,
  "max_possible_score": 20.0,
  "answers": [
    {
      "question_id": "q1",
      "question_text": "Questão sobre números",
      "question_type": "multipleChoice",
      "correct_answer": "A",
      "student_answer": "A",
      "options": ["A", "B", "C", "D"],
      "is_correct": true,
      "score": 1.0
    }
  ]
}
```

### 5. 📊 Estatísticas Gerais
**`GET /evaluation-results/stats`**

Estatísticas gerais do sistema de avaliações.

**Resposta:**
```json
{
  "completed_evaluations": 45,
  "pending_results": 12,
  "total_evaluations": 67,
  "average_score": 72.5,
  "total_students": 1250,
  "average_completion_time": 65,
  "top_performance_subject": "Matemática"
}
```

### 6. 📋 Lista de Avaliações com Resultados
**`GET /evaluation-results/list`**

Lista de avaliações com resultados agregados.

**Resposta:**
```json
[
  {
    "evaluation_id": "test_id",
    "title": "Avaliação de Matemática",
    "subject": "Matemática",
    "grade": "9º Ano",
    "total_students": 25,
    "completed_students": 23,
    "average_score": 72.5,
    "last_updated": "2024-01-02T15:30:00"
  }
]
```

## 🔐 Controle de Acesso

### Papéis e Permissões

| Papel | Acesso às Avaliações | Acesso aos Resultados |
|-------|---------------------|----------------------|
| **Professor** | Apenas suas avaliações | Apenas suas avaliações |
| **Admin** | Todas as avaliações | Todas as avaliações |
| **Coordenador** | Todas as avaliações | Todas as avaliações |
| **Diretor** | Todas as avaliações | Todas as avaliações |

### Implementação de Segurança

```python
# Verificação automática de permissões
if user['role'] == 'professor' and test.created_by != user['id']:
    return jsonify({"error": "Acesso negado"}), 403
```

## 📊 Estrutura de Dados

### Classificações de Proficiência

| Classificação | Descrição | Escala 0-1000 |
|---------------|-----------|----------------|
| **Abaixo do Básico** | Desempenho insuficiente | 0-200 |
| **Básico** | Desempenho básico | 201-400 |
| **Adequado** | Desempenho adequado | 401-600 |
| **Avançado** | Desempenho avançado | 601-1000 |

### Tipos de Questão

- **multipleChoice**: Questões de múltipla escolha (correção automática)
- **essay**: Questões dissertativas (correção manual)
- **discursive**: Questões discursivas (correção manual)

### Status de Avaliação

- **pendente**: Avaliação criada mas não aplicada
- **agendada**: Avaliação aplicada e disponível
- **em_andamento**: Alunos realizando a avaliação
- **concluida**: Avaliação finalizada

## 🛠️ Instalação

### Pré-requisitos

- Python 3.8+
- PostgreSQL 12+
- pip

### Passos de Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/seu-usuario/innovaplay_backend.git
cd innovaplay_backend
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure as variáveis de ambiente**
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. **Configure o banco de dados**
```bash
# Execute as migrações
python migration_all_changes.py
```

## ⚙️ Configuração

### Variáveis de Ambiente

```env
# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@localhost:5432/innovaplay

# JWT
JWT_SECRET_KEY=sua_chave_secreta_aqui

# Configurações da Aplicação
FLASK_ENV=development
FLASK_DEBUG=True

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Configuração do Banco de Dados

1. **Crie o banco PostgreSQL**
```sql
CREATE DATABASE innovaplay;
CREATE USER innovaplay_user WITH PASSWORD 'sua_senha';
GRANT ALL PRIVILEGES ON DATABASE innovaplay TO innovaplay_user;
```

2. **Execute as migrações**
```bash
python migration_all_changes.py
```

## 🚀 Uso

### Iniciar o Servidor

```bash
python run.py
```

O servidor estará disponível em `http://localhost:5000`

### Testar os Endpoints

```bash
# Teste de saúde
curl http://localhost:5000/health

# Listar avaliações (requer autenticação)
curl -H "Authorization: Bearer SEU_TOKEN" \
     http://localhost:5000/evaluation-results/avaliacoes
```

### Exemplo de Uso no Frontend

```javascript
// Listar avaliações do professor
const response = await fetch('/evaluation-results/avaliacoes', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log('Avaliações:', data.data);

// Obter resultados de uma avaliação específica
const resultsResponse = await fetch(`/evaluation-results/alunos?avaliacao_id=${testId}`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const results = await resultsResponse.json();
console.log('Resultados:', results.data);
```

## 📝 Exemplos de Implementação Frontend

### Página de Resultados por Turma

```javascript
// Componente React para exibir resultados por turma
function ClassResults({ testId }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchResults();
  }, [testId]);

  const fetchResults = async () => {
    try {
      const response = await fetch(`/evaluation-results/alunos?avaliacao_id=${testId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      setResults(data.data);
    } catch (error) {
      console.error('Erro ao buscar resultados:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Resultados da Avaliação</h2>
      {loading ? (
        <p>Carregando...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Aluno</th>
              <th>Turma</th>
              <th>Acertos</th>
              <th>Erros</th>
              <th>Nota</th>
              <th>Classificação</th>
            </tr>
          </thead>
          <tbody>
            {results.map(student => (
              <tr key={student.id}>
                <td>{student.nome}</td>
                <td>{student.turma}</td>
                <td>{student.acertos}</td>
                <td>{student.erros}</td>
                <td>{student.nota}</td>
                <td>{student.classificacao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 📞 Suporte

Para suporte, envie um email para suporte@innovaplay.com ou abra uma issue no GitHub.

---

**InnovaPlay Backend** - Sistema completo de gerenciamento de avaliações educacionais