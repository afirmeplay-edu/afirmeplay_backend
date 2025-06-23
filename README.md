# InnovaPlay Backend

## Rotas de Avaliação

### Criar Avaliação
**POST** `/test`

Cria uma nova avaliação com múltiplas disciplinas e questões.

#### Payload de Exemplo:
```json
{
  "title": "Avaliação Diagnóstica 2024",
  "municipalities": ["c1d2e3f4-5678-1234-9abc-def012345678"],
  "schools": ["a1b2c3d4-5678-1234-9abc-def012345678"],
  "course": "b1c2d3e4-5678-1234-9abc-def012345678",
  "grade": "g1h2i3j4-5678-1234-9abc-def012345678",
  "type": "AVALIACAO",
  "model": "SAEB",
  "subjects": [
    { "id": "subj-1", "name": "Matemática" },
    { "id": "subj-2", "name": "Português" }
  ],
  "subject": "",
  "questions": [
    {
      "id": "",
      "title": "Quem descobriu o Brasil?",
      "text": "Explique quem foi o descobridor do Brasil.",
      "secondStatement": "",
      "type": "open",
      "subjectId": "subj-2",
      "subject": { "id": "subj-2", "name": "Português" },
      "grade": { "id": "g1h2i3j4-5678-1234-9abc-def012345678", "name": "Grupo 4" },
      "difficulty": "Fácil",
      "value": "2",
      "solution": "Pedro Álvares Cabral",
      "options": [],
      "skills": ["EF01LP01", "EF01LP02"],
      "created_by": "user-uuid"
    }
  ],
  "created_by": "user-uuid"
}
```

### Aplicar Avaliação às Classes
**POST** `/test/{test_id}/apply`

Aplica uma avaliação a uma ou múltiplas classes com controle de data/hora.

#### Payload de Exemplo:
```json
{
  "classes": [
    {
      "class_id": "class-uuid-1",
      "application": "2024-01-15T10:00:00",
      "expiration": "2024-01-15T12:00:00"
    },
    {
      "class_id": "class-uuid-2",
      "application": "2024-01-16T14:00:00",
      "expiration": "2024-01-16T16:00:00"
    }
  ]
}
```

#### Resposta de Sucesso:
```json
{
  "message": "Test applied to 2 classes successfully",
  "applied_classes": ["class-uuid-1", "class-uuid-2"]
}
```

### Listar Classes da Avaliação
**GET** `/test/{test_id}/classes`

Lista todas as classes onde uma avaliação foi aplicada.

#### Resposta de Exemplo:
```json
[
  {
    "class_test_id": "ct-uuid-1",
    "class": {
      "id": "class-uuid-1",
      "name": "Turma A",
      "school": {
        "id": "school-uuid",
        "name": "Escola Municipal"
      },
      "grade": {
        "id": "grade-uuid",
        "name": "5º Ano"
      }
    },
    "application": "2024-01-15T10:00:00",
    "expiration": "2024-01-15T12:00:00"
  }
]
```

### Remover Aplicação de Avaliação
**DELETE** `/test/{test_id}/classes/{class_id}`

Remove a aplicação de uma avaliação de uma classe específica.

#### Resposta de Sucesso:
```json
{
  "message": "Test application removed successfully"
}
```

## Fluxo de Uso

1. **Criar Avaliação**: Use `POST /test` para criar a avaliação
2. **Aplicar às Classes**: Use `POST /test/{test_id}/apply` para aplicar a avaliação às classes desejadas
3. **Gerenciar Aplicações**: Use `GET /test/{test_id}/classes` para ver onde a avaliação foi aplicada
4. **Remover Aplicação**: Use `DELETE /test/{test_id}/classes/{class_id}` se necessário

## Observações

- A avaliação é criada independentemente das classes
- Uma mesma avaliação pode ser aplicada a múltiplas classes
- Cada aplicação tem controle de data/hora de início e fim
- O sistema previne aplicações duplicadas da mesma avaliação à mesma classe