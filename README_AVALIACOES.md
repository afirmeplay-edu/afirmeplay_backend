# Documentação das Rotas do Fluxo de Avaliações

Esta documentação descreve todas as rotas relacionadas ao fluxo completo de avaliações, desde a criação de questões até a submissão de respostas pelos alunos.

## Índice

1. [Criação de Questões](#criação-de-questões)
2. [Criação de Avaliações](#criação-de-avaliações)
3. [Listagem de Avaliações](#listagem-de-avaliações)
4. [Atualização de Avaliações](#atualização-de-avaliações)
5. [Deletar Avaliações](#deletar-avaliações)
6. [Aplicar Avaliações](#aplicar-avaliações)
7. [Listar Avaliações para Alunos](#listar-avaliações-para-alunos)
8. [Obter Detalhes da Avaliação](#obter-detalhes-da-avaliação)
9. [Controle de Sessões](#controle-de-sessões)
10. [Submissão de Respostas](#submissão-de-respostas)
11. [Resultados e Correção](#resultados-e-correção)

---

## Criação de Questões

### POST /questions

Cria uma nova questão no banco de dados.

**Permissões:** admin, professor, coordenador, diretor

**Body:**
```json
{
  "number": 1,
  "text": "Texto da questão",
  "formattedText": "<p>Texto formatado em HTML</p>",
  "secondStatement": "Segundo enunciado (opcional)",
  "subjectId": "uuid-da-disciplina",
  "title": "Título da questão",
  "description": "Descrição da questão",
  "command": "Comando específico",
  "subtitle": "Subtítulo",
  "options": [
    {
      "text": "Alternativa A",
      "isCorrect": true
    },
    {
      "text": "Alternativa B", 
      "isCorrect": false
    }
  ],
  "skills": ["habilidade1", "habilidade2"],
  "grade": "uuid-da-série",
  "educationStageId": "uuid-do-estagio",
  "difficulty": "facil",
  "solution": "resposta_correta",
  "formattedSolution": "<p>Solução formatada</p>",
  "test_id": "uuid-do-teste (opcional)",
  "type": "multipleChoice",
  "value": 1.0,
  "topics": ["topico1", "topico2"],
  "version": 1,
  "createdBy": "uuid-do-criador",
  "lastModifiedBy": "uuid-do-modificador"
}
```

**Campos Obrigatórios:**
- `text`: Texto da questão
- `type`: Tipo da questão (multipleChoice, etc.)
- `subjectId`: ID da disciplina
- `grade`: ID da série
- `createdBy`: ID do criador

**Resposta de Sucesso (201):**
```json
{
  "message": "Question created successfully",
  "id": "uuid-da-questao"
}
```

---

## Criação de Avaliações

### POST /test

Cria uma nova avaliação.

**Permissões:** admin, professor, coordenador, diretor

**Body:**
```json
{
  "title": "Título da Avaliação",
  "description": "Descrição da avaliação",
  "type": "AVALIACAO",
  "subject": "uuid-da-disciplina",
  "grade": "uuid-da-série",
  "intructions": "Instruções para os alunos",
  "max_score": 100,
  "time_limit": "2024-01-01T10:00:00",
  "end_time": "2024-01-01T12:00:00",
  "duration": 120,
  "evaluation_mode": "virtual",
  "created_by": "uuid-do-criador",
  "municipalities": ["municipio1", "municipio2"],
  "schools": ["uuid-escola1", "uuid-escola2"],
  "course": "curso",
  "model": "modelo",
  "subjects": [
    {
      "id": "uuid-disciplina1",
      "name": "Matemática"
    },
    {
      "id": "uuid-disciplina2", 
      "name": "Português"
    }
  ],
  "questions": [
    {
      "id": "uuid-questao-existente"
    },
    {
      "number": 1,
      "text": "Nova questão",
      "subjectId": "uuid-disciplina",
      "type": "multipleChoice",
      "options": [
        {"text": "A", "isCorrect": true},
        {"text": "B", "isCorrect": false}
      ],
      "created_by": "uuid-criador"
    }
  ]
}
```

**Campos Obrigatórios:**
- `title`: Título da avaliação
- `type`: Tipo (AVALIACAO, SIMULADO)
- `model`: Modelo da avaliação
- `course`: Curso
- `created_by`: ID do criador

**Resposta de Sucesso (201):**
```json
{
  "message": "Test created successfully",
  "id": "uuid-da-avaliacao",
  "classes_applied": 0
}
```

---

## Listagem de Avaliações

### GET /test

Lista todas as avaliações com paginação e filtros.

**Permissões:** admin, professor, coordenador, diretor

**Query Parameters:**
- `page`: Número da página (padrão: 1)
- `per_page`: Itens por página (padrão: 10, máximo: 100)
- `only_count`: true/false - retorna apenas contagem
- `status`: Filtro por status (pendente, agendada, em_andamento, concluida, cancelada)
- `subject_id`: Filtro por disciplina
- `type`: Filtro por tipo
- `model`: Filtro por modelo
- `grade_id`: Filtro por série
- `sort`: Campo para ordenação (created_at, title, status)
- `order`: Ordem (asc, desc)

**Resposta de Sucesso (200):**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Título da Avaliação",
      "description": "Descrição",
      "type": "AVALIACAO",
      "subject": {
        "id": "uuid",
        "name": "Matemática"
      },
      "grade": {
        "id": "uuid",
        "name": "9º Ano"
      },
      "status": "agendada",
      "created_at": "2024-01-01T10:00:00Z",
      "creator": {
        "id": "uuid",
        "name": "Nome do Professor",
        "email": "professor@email.com"
      },
      "total_questions": 20,
      "max_score": 100,
      "duration": 120
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 50,
    "pages": 5,
    "has_next": true,
    "has_prev": false,
    "next_num": 2,
    "prev_num": null
  }
}
```

### GET /test/user/{user_id}

Lista avaliações criadas por um usuário específico.

**Permissões:** admin, professor, coordenador, diretor

**Resposta de Sucesso (200):**
```json
[
  {
    "id": "uuid",
    "title": "Título da Avaliação",
    "description": "Descrição",
    "type": "AVALIACAO",
    "status": "agendada",
    "created_at": "2024-01-01T10:00:00Z",
    "questions": [
      {
        "id": "uuid",
        "number": 1,
        "text": "Texto da questão",
        "alternatives": [
          {"text": "A", "isCorrect": true},
          {"text": "B", "isCorrect": false}
        ]
      }
    ]
  }
]
```

---

## Atualização de Avaliações

### PUT /test/{test_id}

Atualiza uma avaliação existente.

**Permissões:** admin, professor, coordenador, diretor

**Body:**
```json
{
  "title": "Novo Título",
  "description": "Nova descrição",
  "type": "AVALIACAO",
  "subject": "uuid-da-disciplina",
  "grade_id": "uuid-da-série",
  "max_score": 100,
  "time_limit": "2024-01-01T10:00:00",
  "end_time": "2024-01-01T12:00:00",
  "duration": 120,
  "evaluation_mode": "virtual",
  "intructions": "Novas instruções",
  "municipalities": ["municipio1"],
  "schools": ["uuid-escola1"],
  "course": "curso",
  "model": "modelo",
  "subjects": [
    {
      "id": "uuid-disciplina1",
      "name": "Matemática"
    }
  ]
}
```

**Resposta de Sucesso (200):**
```json
{
  "message": "Test updated successfully"
}
```

---

## Deletar Avaliações

### DELETE /test/{test_id}

Deleta uma avaliação específica.

**Permissões:** admin, professor, coordenador, diretor

**Resposta de Sucesso (200):**
```json
{
  "message": "Test and all related records deleted successfully"
}
```

### DELETE /test

Deleta múltiplas avaliações em massa.

**Permissões:** admin, professor, coordenador, diretor

**Body:**
```json
{
  "ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Resposta de Sucesso (200):**
```json
{
  "message": "3 tests deleted successfully"
}
```

---

## Aplicar Avaliações

### POST /test/{test_id}/apply

Aplica uma avaliação a uma ou múltiplas classes.

**Permissões:** admin, professor, coordenador, diretor

**Body:**
```json
{
  "classes": [
    {
      "class_id": "uuid-da-classe1",
      "application": "2024-01-01T08:00:00",
      "expiration": "2024-01-01T12:00:00"
    },
    {
      "class_id": "uuid-da-classe2",
      "application": "2024-01-01T08:00:00",
      "expiration": "2024-01-01T12:00:00"
    }
  ]
}
```

**Resposta de Sucesso (201):**
```json
{
  "message": "Test applied/updated to 2 classes successfully",
  "applied_classes": ["uuid-classe1", "uuid-classe2"]
}
```

### GET /test/{test_id}/classes

Lista todas as classes onde uma avaliação foi aplicada.

**Permissões:** admin, professor, coordenador, diretor

**Resposta de Sucesso (200):**
```json
[
  {
    "class_test_id": "uuid",
    "class": {
      "id": "uuid",
      "name": "9º Ano A",
      "school": {
        "id": "uuid",
        "name": "Escola Municipal"
      },
      "grade": {
        "id": "uuid",
        "name": "9º Ano"
      }
    },
    "students_count": 25,
    "application": "2024-01-01T08:00:00Z",
    "expiration": "2024-01-01T12:00:00Z",
    "status": "applied"
  }
]
```

### DELETE /test/{test_id}/classes/{class_id}

Remove a aplicação de uma avaliação de uma classe específica.

**Permissões:** admin, professor, coordenador, diretor

**Resposta de Sucesso (200):**
```json
{
  "message": "Test application removed successfully"
}
```

---

## Listar Avaliações para Alunos

### GET /test/my-class/tests

Lista todas as avaliações disponíveis para o aluno autenticado.

**Permissões:** aluno

**Resposta de Sucesso (200):**
```json
{
  "student": {
    "id": "uuid",
    "name": "Nome do Aluno",
    "user_id": "uuid"
  },
  "class": {
    "id": "uuid",
    "name": "9º Ano A",
    "school": {
      "id": "uuid",
      "name": "Escola Municipal"
    },
    "grade": {
      "id": "uuid",
      "name": "9º Ano"
    }
  },
  "total_tests": 3,
  "tests": [
    {
      "test_id": "uuid",
      "title": "Avaliação de Matemática",
      "description": "Descrição da avaliação",
      "type": "AVALIACAO",
      "subject": {
        "id": "uuid",
        "name": "Matemática"
      },
      "subjects": [
        {
          "id": "uuid",
          "name": "Matemática"
        }
      ],
      "grade": {
        "id": "uuid",
        "name": "9º Ano"
      },
      "intructions": "Instruções para os alunos",
      "max_score": 100,
      "time_limit": "2024-01-01T10:00:00Z",
      "duration": 120,
      "course": "curso",
      "model": "modelo",
      "subjects_info": [
        {
          "id": "uuid",
          "name": "Matemática"
        }
      ],
      "status": "agendada",
      "creator": {
        "id": "uuid",
        "name": "Nome do Professor"
      },
      "total_questions": 20,
      "application_info": {
        "class_test_id": "uuid",
        "application": "2024-01-01T08:00:00Z",
        "expiration": "2024-01-01T12:00:00Z",
        "current_time": "2024-01-01T09:00:00Z"
      },
      "availability": {
        "is_available": true,
        "status": "available"
      },
      "student_status": {
        "has_completed": false,
        "status": "nao_iniciada",
        "completed_at": null,
        "score": null,
        "grade": null,
        "can_start": true
      }
    }
  ]
}
```

### GET /test/class/{class_id}/tests/complete

Obtém todas as avaliações aplicadas a uma classe com detalhes completos.

**Permissões:** admin, professor, coordenador, diretor, aluno

**Resposta de Sucesso (200):**
```json
{
  "class": {
    "id": "uuid",
    "name": "9º Ano A",
    "school": {
      "id": "uuid",
      "name": "Escola Municipal"
    },
    "grade": {
      "id": "uuid",
      "name": "9º Ano"
    }
  },
  "total_tests": 2,
  "tests": [
    {
      "test": {
        "id": "uuid",
        "title": "Avaliação de Matemática",
        "description": "Descrição",
        "type": "AVALIACAO",
        "subject": {
          "id": "uuid",
          "name": "Matemática"
        },
        "grade": {
          "id": "uuid",
          "name": "9º Ano"
        },
        "intructions": "Instruções",
        "max_score": 100,
        "time_limit": "2024-01-01T10:00:00Z",
        "duration": 120,
        "course": "curso",
        "model": "modelo",
        "subjects_info": [
          {
            "id": "uuid",
            "name": "Matemática"
          }
        ],
        "status": "agendada",
        "created_by": "uuid",
        "creator": {
          "id": "uuid",
          "name": "Nome do Professor",
          "email": "professor@email.com"
        }
      },
      "class_test_info": {
        "class_test_id": "uuid",
        "application": "2024-01-01T08:00:00Z",
        "expiration": "2024-01-01T12:00:00Z",
        "status": "pendente"
      },
      "availability": {
        "is_available": true,
        "status": "available",
        "current_time": "2024-01-01T09:00:00Z"
      },
      "questions": [
        {
          "id": "uuid",
          "number": 1,
          "text": "Texto da questão",
          "formatted_text": "<p>Texto formatado</p>",
          "title": "Título da questão",
          "description": "Descrição",
          "command": "Comando",
          "subtitle": "Subtítulo",
          "alternatives": [
            {"text": "A", "isCorrect": false},
            {"text": "B", "isCorrect": true},
            {"text": "C", "isCorrect": false},
            {"text": "D", "isCorrect": false}
          ],
          "question_type": "multipleChoice",
          "value": 1.0,
          "topics": ["topico1"],
          "subject": {
            "id": "uuid",
            "name": "Matemática"
          },
          "grade": {
            "id": "uuid",
            "name": "9º Ano"
          },
          "education_stage": {
            "id": "uuid",
            "name": "Ensino Fundamental"
          }
        }
      ],
      "total_questions": 20,
      "total_value": 20.0
    }
  ]
}
```

---

## Obter Detalhes da Avaliação

### GET /test/{test_id}

Obtém detalhes completos de uma avaliação específica.

**Permissões:** admin, professor, coordenador, diretor, aluno

**Resposta de Sucesso (200):**
```json
{
  "id": "uuid",
  "title": "Título da Avaliação",
  "description": "Descrição",
  "type": "AVALIACAO",
  "subject": {
    "id": "uuid",
    "name": "Matemática"
  },
  "grade": {
    "id": "uuid",
    "name": "9º Ano"
  },
  "intructions": "Instruções",
  "max_score": 100,
  "time_limit": "2024-01-01T10:00:00Z",
  "end_time": "2024-01-01T12:00:00Z",
  "duration": 120,
  "evaluation_mode": "virtual",
  "course": "curso",
  "model": "modelo",
  "subjects_info": [
    {
      "id": "uuid",
      "name": "Matemática"
    }
  ],
  "status": "agendada",
  "created_at": "2024-01-01T08:00:00Z",
  "creator": {
    "id": "uuid",
    "name": "Nome do Professor",
    "email": "professor@email.com"
  },
  "questions": [
    {
      "id": "uuid",
      "number": 1,
      "text": "Texto da questão",
      "formatted_text": "<p>Texto formatado</p>",
      "title": "Título",
      "description": "Descrição",
      "command": "Comando",
      "subtitle": "Subtítulo",
      "alternatives": [
        {"text": "A", "isCorrect": false},
        {"text": "B", "isCorrect": true}
      ],
      "question_type": "multipleChoice",
      "value": 1.0,
      "topics": ["topico1"],
      "subject": {
        "id": "uuid",
        "name": "Matemática"
      },
      "grade": {
        "id": "uuid",
        "name": "9º Ano"
      },
      "education_stage": {
        "id": "uuid",
        "name": "Ensino Fundamental"
      },
      "creator": {
        "id": "uuid",
        "name": "Nome do Criador"
      },
      "last_modifier": {
        "id": "uuid",
        "name": "Nome do Modificador"
      }
    }
  ]
}
```

### GET /test/{test_id}/details

Alias para obter detalhes da avaliação (mesmo que GET /test/{test_id}).

---

## Controle de Sessões

### POST /test/{test_id}/start-session

Inicia uma nova sessão de teste para o aluno autenticado.

**Permissões:** aluno

**Resposta de Sucesso (201):**
```json
{
  "message": "Sessão iniciada com sucesso",
  "session_id": "uuid-da-sessao",
  "started_at": "2024-01-01T09:00:00Z",
  "time_limit_minutes": 120
}
```

**Resposta se já existe sessão ativa (200):**
```json
{
  "message": "Sessão já iniciada",
  "session_id": "uuid-da-sessao",
  "started_at": "2024-01-01T09:00:00Z",
  "time_limit_minutes": 120
}
```

### GET /test/{test_id}/session-info

Retorna informações da sessão para o frontend calcular o tempo.

**Permissões:** aluno

**Resposta de Sucesso (200):**
```json
{
  "session_id": "uuid",
  "started_at": "2024-01-01T09:00:00Z",
  "time_limit_minutes": 120,
  "elapsed_minutes": 30,
  "remaining_minutes": 90,
  "is_expired": false,
  "session_exists": true
}
```

### GET /student-answers/sessions/{session_id}/status

Retorna o status atual da sessão.

**Permissões:** student, admin, professor, aluno

**Resposta de Sucesso (200):**
```json
{
  "session_id": "uuid",
  "status": "em_andamento",
  "started_at": "2024-01-01T09:00:00Z",
  "submitted_at": null,
  "time_limit_minutes": 120,
  "elapsed_minutes": 30,
  "remaining_minutes": 90,
  "is_expired": false,
  "total_questions": 20,
  "correct_answers": 0,
  "score": null,
  "grade": null
}
```

### POST /student-answers/sessions/{session_id}/end

Finaliza uma sessão de teste.

**Permissões:** student, admin, professor, aluno

**Body:**
```json
{
  "reason": "finalizado_pelo_aluno"
}
```

**Resposta de Sucesso (200):**
```json
{
  "message": "Sessão finalizada com sucesso",
  "session_id": "uuid",
  "finalized_at": "2024-01-01T11:00:00Z",
  "duration_minutes": 120,
  "status": "finalizada"
}
```

### PATCH /student-answers/sessions/{session_id}/timer

Atualiza o timer da sessão.

**Permissões:** student, admin, professor, aluno

**Body:**
```json
{
  "elapsed_minutes": 45,
  "remaining_minutes": 75
}
```

**Resposta de Sucesso (200):**
```json
{
  "message": "Timer atualizado com sucesso",
  "session_id": "uuid",
  "elapsed_minutes": 45,
  "remaining_minutes": 75
}
```

---

## Submissão de Respostas

### POST /student-answers/submit

Submete as respostas do aluno e finaliza a sessão.

**Permissões:** student, admin, professor, aluno

**Body:**
```json
{
  "session_id": "uuid-da-sessao",
  "answers": [
    {
      "question_id": "uuid-da-questao1",
      "answer": "A"
    },
    {
      "question_id": "uuid-da-questao2",
      "answer": "B"
    }
  ]
}
```

**Resposta de Sucesso (201):**
```json
{
  "message": "Respostas salvas e sessão finalizada com sucesso",
  "session_id": "uuid",
  "submitted_at": "2024-01-01T11:00:00Z",
  "duration_minutes": 120,
  "results": {
    "total_questions": 20,
    "correct_answers": 15,
    "score_percentage": 75.0,
    "grade": 7.5,
    "answers_saved": 20
  },
  "answers": [
    {
      "question_id": "uuid",
      "answer": "A",
      "answered_at": "2024-01-01T11:00:00Z"
    }
  ]
}
```

### POST /student-answers/save-partial

Salva respostas parciais sem finalizar a sessão.

**Permissões:** student, admin, professor, aluno

**Body:**
```json
{
  "session_id": "uuid-da-sessao",
  "answers": [
    {
      "question_id": "uuid-da-questao1",
      "answer": "A"
    }
  ]
}
```

**Resposta de Sucesso (200):**
```json
{
  "message": "Respostas parciais salvas com sucesso",
  "session_id": "uuid",
  "answers_saved": 1,
  "answers": [
    {
      "question_id": "uuid",
      "answer": "A",
      "answered_at": "2024-01-01T10:30:00Z"
    }
  ]
}
```

### GET /student-answers/active-session/{test_id}

Obtém a sessão ativa para um teste específico.

**Permissões:** student, admin, professor, aluno

**Resposta de Sucesso (200):**
```json
{
  "session_exists": true,
  "session": {
    "id": "uuid",
    "status": "em_andamento",
    "started_at": "2024-01-01T09:00:00Z",
    "time_limit_minutes": 120,
    "elapsed_minutes": 30,
    "remaining_minutes": 90,
    "is_expired": false
  },
  "saved_answers": [
    {
      "question_id": "uuid",
      "answer": "A",
      "answered_at": "2024-01-01T10:30:00Z"
    }
  ]
}
```

---

## Resultados e Correção

### GET /student-answers/student/{test_id}/status

Verifica o status de uma avaliação específica para o aluno autenticado.

**Permissões:** student, admin, professor, aluno

**Resposta de Sucesso (200):**
```json
{
  "test_id": "uuid",
  "student_id": "uuid",
  "has_completed": true,
  "session_status": "finalizada",
  "completed_at": "2024-01-01T11:00:00Z",
  "score": 75.0,
  "grade": 7.5,
  "total_questions": 20,
  "correct_answers": 15,
  "has_answers": true,
  "can_start": false
}
```

### GET /student-answers/student/tests/status

Obtém o status de todas as avaliações do aluno.

**Permissões:** student, admin, professor, aluno

**Query Parameters:**
- `class_id`: ID da classe (opcional, usa classe do aluno se não fornecido)

**Resposta de Sucesso (200):**
```json
{
  "student_id": "uuid",
  "class_id": "uuid",
  "tests_status": [
    {
      "test_id": "uuid",
      "title": "Avaliação de Matemática",
      "has_completed": true,
      "session_status": "finalizada",
      "completed_at": "2024-01-01T11:00:00Z",
      "score": 75.0,
      "grade": 7.5,
      "total_questions": 20,
      "correct_answers": 15,
      "can_start": false
    }
  ]
}
```

### GET /student-answers/session/{session_id}/answers

Retorna todas as respostas de uma sessão específica.

**Permissões:** student, admin, professor, aluno

**Resposta de Sucesso (200):**
```json
{
  "session_id": "uuid",
  "total_answers": 20,
  "answers": [
    {
      "question_id": "uuid",
      "answer": "A",
      "answered_at": "2024-01-01T11:00:00Z",
      "is_correct": true,
      "manual_points": null,
      "feedback": null
    }
  ]
}
```

### GET /student-answers/student/sessions

Obtém todas as sessões do aluno autenticado.

**Permissões:** student, admin, professor, aluno

**Query Parameters:**
- `status`: Filtro por status da sessão
- `test_id`: Filtro por ID do teste

**Resposta de Sucesso (200):**
```json
{
  "student_id": "uuid",
  "total_sessions": 5,
  "sessions": [
    {
      "id": "uuid",
      "test_id": "uuid",
      "test_title": "Avaliação de Matemática",
      "status": "finalizada",
      "started_at": "2024-01-01T09:00:00Z",
      "submitted_at": "2024-01-01T11:00:00Z",
      "duration_minutes": 120,
      "score": 75.0,
      "grade": 7.5,
      "total_questions": 20,
      "correct_answers": 15
    }
  ]
}
```

### GET /student-answers/student/{test_id}/can-start

Verifica se um aluno pode iniciar uma avaliação específica.

**Permissões:** student, admin, professor, aluno

**Resposta de Sucesso (200):**
```json
{
  "can_start": true,
  "reason": "Avaliação disponível",
  "test_info": {
    "id": "uuid",
    "title": "Avaliação de Matemática",
    "status": "agendada"
  },
  "student_info": {
    "id": "uuid",
    "session_status": "nao_iniciada",
    "has_completed": false
  }
}
```

---

## Endpoints de Debug

### GET /test/debug/dates/{test_id}

Endpoint de debug para verificar as datas de uma avaliação.

**Permissões:** admin, professor, coordenador, diretor, aluno

**Resposta de Sucesso (200):**
```json
{
  "test_id": "uuid",
  "test_title": "Avaliação de Matemática",
  "test_status": "agendada",
  "current_time": "2024-01-01T09:00:00Z",
  "current_time_utc": "2024-01-01T12:00:00Z",
  "class_tests": [
    {
      "class_test_id": "uuid",
      "class_id": "uuid",
      "application_original": "2024-01-01T08:00:00Z",
      "application_timezone_aware": "2024-01-01T05:00:00Z",
      "expiration_original": "2024-01-01T12:00:00Z",
      "expiration_timezone_aware": "2024-01-01T09:00:00Z",
      "current_time": "2024-01-01T09:00:00Z",
      "is_application_passed": true,
      "is_expired": false,
      "time_until_application": "-4:00:00",
      "time_until_expiration": "0:00:00"
    }
  ]
}
```

### GET /test/debug/subjects/{test_id}

Endpoint de debug para verificar os subjects de uma avaliação.

**Permissões:** admin, professor, coordenador, diretor, aluno

**Resposta de Sucesso (200):**
```json
{
  "test_id": "uuid",
  "test_title": "Avaliação de Matemática",
  "subject_field": "uuid-disciplina",
  "subject_rel": {
    "id": "uuid",
    "name": "Matemática"
  },
  "subjects_info": [
    {
      "id": "uuid",
      "name": "Matemática"
    }
  ],
  "subjects_info_type": "list",
  "parsed_subjects": [
    {
      "index": 0,
      "from_db": true,
      "id": "uuid",
      "name": "Matemática",
      "original_data": {
        "id": "uuid",
        "name": "Matemática"
      }
    }
  ]
}
```

---

## Códigos de Status HTTP

- **200**: Sucesso
- **201**: Criado com sucesso
- **400**: Dados inválidos ou campos obrigatórios ausentes
- **401**: Não autenticado
- **403**: Acesso negado (sem permissão)
- **404**: Recurso não encontrado
- **410**: Recurso expirado (tempo limite excedido)
- **500**: Erro interno do servidor

---

## Observações Importantes

1. **Autenticação**: Todas as rotas requerem autenticação JWT
2. **Permissões**: Cada rota tem restrições específicas de permissão
3. **Fuso Horário**: As datas são tratadas no fuso horário do Brasil (UTC-3)
4. **Paginação**: Rotas de listagem suportam paginação
5. **Validação**: Todos os dados são validados antes do processamento
6. **Logs**: Todas as operações são registradas em logs para auditoria
7. **Transações**: Operações críticas usam transações de banco de dados
8. **CORS**: Configurado para permitir requisições do frontend

---

## Exemplos de Uso

### Fluxo Completo de uma Avaliação

1. **Criar Questões**: `POST /questions`
2. **Criar Avaliação**: `POST /test`
3. **Aplicar Avaliação**: `POST /test/{test_id}/apply`
4. **Aluno Lista Avaliações**: `GET /test/my-class/tests`
5. **Aluno Inicia Sessão**: `POST /test/{test_id}/start-session`
6. **Aluno Salva Respostas Parciais**: `POST /student-answers/save-partial`
7. **Aluno Submete Avaliação**: `POST /student-answers/submit`
8. **Professor Verifica Resultados**: `GET /student-answers/student/{test_id}/status`

### Verificação de Disponibilidade

```javascript
// Verificar se aluno pode iniciar avaliação
const response = await fetch('/student-answers/student/{test_id}/can-start', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();

if (data.can_start) {
  // Iniciar sessão
  await fetch('/test/{test_id}/start-session', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` }
  });
}
```

### Controle de Tempo

```javascript
// Obter informações da sessão para timer
const response = await fetch('/test/{test_id}/session-info', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const sessionInfo = await response.json();

// Usar remaining_minutes para exibir timer no frontend
const remainingTime = sessionInfo.remaining_minutes;
``` 