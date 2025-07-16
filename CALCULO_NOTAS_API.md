# API de Cálculo de Notas - Documentação para Frontend

## Visão Geral

Esta documentação descreve os endpoints para cálculo de notas, correção manual de questões dissertativas e consulta de resultados de avaliações.

## Base URL
```
/evaluation-results
```

## Autenticação
Todos os endpoints requerem autenticação JWT. Inclua o token no header:
```
Authorization: Bearer <seu_token_jwt>
```

---

## 1. Calcular Notas de um Teste

### Endpoint
```
POST /evaluation-results/{test_id}/calculate-scores
```

### Descrição
Calcula as notas de todos os alunos para uma avaliação específica. Suporta correção automática para questões de múltipla escolha e aguarda correção manual para questões dissertativas.

### Permissões
- admin, professor, coordenador, diretor
- Professor só pode calcular notas de testes que criou

### Body (Opcional)
```json
{
  "student_ids": ["uuid1", "uuid2"]
}
```

### Exemplo de Requisição
```javascript
const response = await fetch('/evaluation-results/test-123/calculate-scores', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({
    student_ids: ["student-1", "student-2"] // opcional
  })
});
```

### Exemplo de Resposta
```json
{
  "test_id": "test-123",
  "test_title": "Avaliação de Matemática",
  "total_students": 25,
  "total_questions": 10,
  "calculation_timestamp": "2024-01-15T10:30:00Z",
  "results": {
    "student-1": {
      "total_questions": 10,
      "answered_questions": 10,
      "correct_answers": 7,
      "multiple_choice_questions": 8,
      "essay_questions": 2,
      "pending_corrections": 1,
      "corrected_essays": 1,
      "score_percentage": 87.5,
      "total_score": 8.5,
      "max_possible_score": 10.0
    },
    "student-2": {
      "total_questions": 10,
      "answered_questions": 9,
      "correct_answers": 6,
      "multiple_choice_questions": 8,
      "essay_questions": 2,
      "pending_corrections": 2,
      "corrected_essays": 0,
      "score_percentage": 75.0,
      "total_score": 6.0,
      "max_possible_score": 10.0
    }
  }
}
```

---

## 2. Listar Questões Pendentes de Correção

### Endpoint
```
GET /evaluation-results/{test_id}/pending-corrections
```

### Descrição
Lista todas as questões dissertativas que ainda precisam de correção manual.

### Permissões
- admin, professor, coordenador, diretor
- Professor só pode ver correções de testes que criou

### Query Parameters
- `student_id` (opcional): Filtrar por aluno específico
- `question_id` (opcional): Filtrar por questão específica

### Exemplo de Requisição
```javascript
const response = await fetch('/evaluation-results/test-123/pending-corrections?student_id=student-1', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
```

### Exemplo de Resposta
```json
{
  "test_id": "test-123",
  "test_title": "Avaliação de Matemática",
  "total_pending": 3,
  "pending_corrections": [
    {
      "student_answer_id": "answer-1",
      "student_id": "student-1",
      "student_name": "João Silva",
      "question_id": "question-5",
      "question_number": 5,
      "question_text": "Explique o conceito de derivada",
      "question_value": 2.0,
      "student_answer": "A derivada é a taxa de variação instantânea...",
      "answered_at": "2024-01-15T09:30:00Z"
    }
  ]
}
```

---

## 3. Correção Manual Individual

### Endpoint
```
POST /evaluation-results/{test_id}/manual-correction
```

### Descrição
Permite ao professor corrigir uma questão dissertativa específica.

### Permissões
- admin, professor, coordenador, diretor
- Professor só pode corrigir testes que criou

### Body
```json
{
  "student_id": "uuid",
  "question_id": "uuid",
  "score": 85.5,
  "feedback": "Boa resposta, mas poderia ser mais detalhada",
  "is_correct": true
}
```

### Campos
- `student_id` (obrigatório): ID do usuário do aluno (user_id) ou ID da tabela Student
- `question_id` (obrigatório): ID da questão
- `score` (obrigatório): Pontuação de 0 a 100
- `feedback` (opcional): Comentário do professor
- `is_correct` (opcional): true/false (se não fornecido, calculado automaticamente: score > 50)

### Exemplo de Requisição
```javascript
const response = await fetch('/evaluation-results/test-123/manual-correction', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({
    student_id: "student-1",
    question_id: "question-5",
    score: 85.5,
    feedback: "Excelente explicação do conceito",
    is_correct: true
  })
});
```

### Exemplo de Resposta
```json
{
  "message": "Correção salva com sucesso",
  "student_id": "student-1",
  "question_id": "question-5",
  "score": 85.5,
  "corrected_at": "2024-01-15T11:00:00Z"
}
```

---

## 4. Correção Manual em Lote

### Endpoint
```
POST /evaluation-results/{test_id}/batch-correction
```

### Descrição
Permite ao professor corrigir múltiplas questões dissertativas de uma vez.

### Permissões
- admin, professor, coordenador, diretor
- Professor só pode corrigir testes que criou

### Body
```json
{
  "corrections": [
    {
      "student_id": "uuid1",
      "question_id": "uuid",
      "score": 85.5,
      "feedback": "Boa resposta",
      "is_correct": true
    },
    {
      "student_id": "uuid2",
      "question_id": "uuid",
      "score": 70.0,
      "feedback": "Resposta parcialmente correta"
    }
  ]
}
```

**Nota:** O `student_id` pode ser o `user_id` do aluno ou o `id` da tabela Student.

### Exemplo de Requisição
```javascript
const response = await fetch('/evaluation-results/test-123/batch-correction', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + token
  },
  body: JSON.stringify({
    corrections: [
      {
        student_id: "student-1",
        question_id: "question-5",
        score: 85.5,
        feedback: "Excelente explicação"
      },
      {
        student_id: "student-2",
        question_id: "question-5",
        score: 70.0,
        feedback: "Resposta parcialmente correta"
      }
    ]
  })
});
```

### Exemplo de Resposta
```json
{
  "message": "Processadas 2 correções com sucesso",
  "processed": 2,
  "errors": null
}
```

---

## 5. Resultados Detalhados de um Aluno

### Endpoint
```
GET /evaluation-results/{test_id}/student/{student_id}/results
```

### Descrição
Retorna os resultados detalhados de um aluno específico em um teste.

### Permissões
- admin, professor, coordenador, diretor, aluno
- Aluno só pode ver seus próprios resultados
- Professor só pode ver resultados de testes que criou

### Query Parameters
- `include_answers` (opcional): true/false para incluir respostas detalhadas

### Exemplo de Requisição
```javascript
const response = await fetch('/evaluation-results/test-123/student/student-1/results?include_answers=true', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + token
  }
});
```

### Exemplo de Resposta
```json
{
  "test_id": "test-123",
  "student_id": "user-123",  // user_id do aluno
  "student_db_id": "student-456",  // id da tabela Student
  "total_questions": 10,
  "answered_questions": 10,
  "correct_answers": 7,
  "score_percentage": 70.0,
  "total_score": 7.0,
  "max_possible_score": 10.0,
  "answers": [
    {
      "question_id": "question-1",
      "question_number": 1,
      "question_text": "Qual é a raiz quadrada de 16?",
      "question_type": "multipleChoice",
      "question_value": 1.0,
      "student_answer": "C",
      "answered_at": "2024-01-15T09:30:00Z",
      "is_correct": true,
      "score": 1.0,
      "feedback": null,
      "corrected_by": null,
      "corrected_at": null
    },
    {
      "question_id": "question-5",
      "question_number": 5,
      "question_text": "Explique o conceito de derivada",
      "question_type": "essay",
      "question_value": 2.0,
      "student_answer": "A derivada é a taxa de variação...",
      "answered_at": "2024-01-15T09:35:00Z",
      "is_correct": true,
      "score": 1.7,
      "manual_score": 85.5,
      "feedback": "Excelente explicação",
      "corrected_by": "professor-1",
      "corrected_at": "2024-01-15T11:00:00Z"
    }
  ]
}
```

---

## Estrutura das Questões

### Questão de Múltipla Escolha
```json
{
  "id": "question-1",
  "text": "Qual é a raiz quadrada de 16?",
  "question_type": "multipleChoice",
  "alternatives": [
    {"id": "A", "text": "2", "isCorrect": false},
    {"id": "B", "text": "3", "isCorrect": false},
    {"id": "C", "text": "4", "isCorrect": true},
    {"id": "D", "text": "5", "isCorrect": false}
  ],
  "value": 1.0
}
```

### Questão Dissertativa
```json
{
  "id": "question-5",
  "text": "Explique o conceito de derivada",
  "question_type": "essay",
  "value": 2.0
}
```

---

## Fluxo de Trabalho Recomendado

1. **Aluno responde a prova** → Frontend envia respostas via `/student-answers/submit`
2. **Professor calcula notas** → `/evaluation-results/{test_id}/calculate-scores`
3. **Professor vê questões pendentes** → `/evaluation-results/{test_id}/pending-corrections`
4. **Professor corrige questões** → `/evaluation-results/{test_id}/manual-correction` ou `/batch-correction`
5. **Professor recalcula notas** → `/evaluation-results/{test_id}/calculate-scores`
6. **Aluno vê resultados** → `/evaluation-results/{test_id}/student/{student_id}/results`

---

## Códigos de Status HTTP

- `200`: Sucesso
- `201`: Criado com sucesso
- `207`: Multi-Status (alguns itens processados com sucesso, outros com erro)
- `400`: Dados inválidos
- `401`: Não autenticado
- `403`: Acesso negado
- `404`: Recurso não encontrado
- `500`: Erro interno do servidor

---

## Tratamento de Erros

Todos os endpoints retornam erros no formato:
```json
{
  "error": "Descrição do erro",
  "details": "Detalhes técnicos (opcional)"
}
```

## Observações Importantes

1. **IDs das alternativas**: Para questões de múltipla escolha, o frontend deve enviar o ID da alternativa escolhida (ex: "C") no campo `answer` da tabela `student_answers`.

2. **Correção automática**: Questões de múltipla escolha são corrigidas automaticamente comparando o ID da resposta com o ID da alternativa que tem `isCorrect: true`.

3. **Correção manual**: Questões dissertativas (`question_type: "essay"`) requerem correção manual pelo professor.

4. **Permissões**: Professores só podem acessar testes que criaram.

5. **Cálculo de notas**: O percentual é calculado apenas com base nas questões corrigidas automaticamente (múltipla escolha).

6. **IDs de alunos**: O sistema aceita tanto `user_id` quanto `student_id` (ID da tabela Student) nos endpoints. O frontend pode enviar qualquer um dos dois. 