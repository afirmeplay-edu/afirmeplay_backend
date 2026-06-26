# Integração de Cartões de Resposta no Mobile

Documentação da integração entre cartões de resposta e o aplicativo mobile offline.

## Visão Geral

O sistema permite que professores baixem gabaritos de cartões de resposta junto com avaliações online no app mobile, e marquem as respostas dos alunos manualmente (sem usar câmera/OMR).

## Arquitetura

### Dois Sistemas Separados no Mesmo App

1. **Avaliações Online** (já existente)
   - Questões completas com enunciados e imagens
   - Aluno responde no app
   - Dados: `tests`, `questions_by_test`, `student_test_links`

2. **Cartões Resposta** (novo)
   - Apenas estrutura de gabarito (questões e alternativas)
   - Professor marca respostas do papel no app
   - Dados: `answer_sheet_gabaritos`, `student_gabarito_links`

### Estrutura do Bundle

O bundle mobile agora inclui ambos os sistemas:

```json
{
  "sync_bundle_version": 1,
  "bundle_valid_until": "2026-12-31T23:59:59Z",
  "school_id": "uuid",
  
  "students": [...],
  
  "tests": {...},
  "questions_by_test": {...},
  "student_test_links": [...],
  
  "answer_sheet_gabaritos": {
    "gabarito-uuid": {
      "gabarito_id": "uuid",
      "title": "Matemática 5º Ano",
      "num_questions": 25,
      "use_blocks": true,
      "blocks": [
        {
          "subject_name": "Matemática",
          "questions": [
            {"q": 1, "alternatives": ["A", "B", "C", "D"]},
            {"q": 2, "alternatives": ["A", "B", "C", "D", "E"]}
          ]
        }
      ]
    }
  },
  "student_gabarito_links": [
    {"student_id": "uuid", "gabarito_id": "uuid"}
  ]
}
```

## Endpoints Mobile

### 1. Download do Bundle (já existente, agora inclui gabaritos)

```
GET /mobile/v1/sync/bundle?school_id=xxx&page=1
Authorization: Bearer <token>
X-Device-Id: <uuid-v4>
```

**Resposta:** Bundle completo com testes online + gabaritos

---

### 2. Listar Alunos de um Gabarito

```
GET /mobile/v1/answer-sheets/gabaritos/{gabarito_id}/students
Authorization: Bearer <token>
X-Device-Id: <uuid-v4>

Query params (opcionais):
  - class_id: filtrar por turma
  - grade_id: filtrar por série
  - school_id: filtrar por escola
  - flat: true para lista plana
```

**Resposta:**
```json
{
  "gabarito_id": "uuid",
  "gabarito_title": "Matemática 5º Ano",
  "num_questions": 25,
  "classes": [
    {
      "class_id": "uuid",
      "class_name": "5º A",
      "students": [
        {
          "student_id": "uuid",
          "name": "João Silva",
          "has_result": false,
          "can_manual_correct": true
        }
      ]
    }
  ]
}
```

---

### 3. Obter Formulário de Entrada Manual

```
GET /mobile/v1/answer-sheets/manual-entry/form?gabarito_id=xxx&student_id=yyy
Authorization: Bearer <token>
X-Device-Id: <uuid-v4>
```

**Resposta:**
```json
{
  "gabarito_id": "uuid",
  "title": "Matemática 5º Ano",
  "num_questions": 25,
  "blocks": [
    {
      "subject_name": "Matemática",
      "questions": [
        {"q": 1, "alternatives": ["A", "B", "C", "D"]},
        {"q": 2, "alternatives": ["A", "B", "C", "D", "E"]}
      ]
    }
  ],
  "student": {
    "id": "uuid",
    "name": "João Silva"
  },
  "saved_answers": {},
  "existing_result_id": null
}
```

---

### 4. Enviar Respostas Manuais (Individual)

```
POST /mobile/v1/answer-sheets/manual-entry/submit
Authorization: Bearer <token>
X-Device-Id: <uuid-v4>
Content-Type: application/json

{
  "gabarito_id": "uuid",
  "student_id": "uuid",
  "answers": {
    "1": "A",
    "2": "B",
    "3": null,
    "4": "INVALID"
  },
  "device_id": "uuid-v4",
  "offline_submission_id": "uuid-local"
}
```

**Resposta:**
```json
{
  "message": "Respostas registradas com sucesso",
  "detection_method": "manual",
  "student_id": "uuid",
  "student_name": "João Silva",
  "gabarito_id": "uuid",
  "correct": 18,
  "wrong": 5,
  "blank": 2,
  "total": 25,
  "score": 72.0,
  "proficiency": 245.5,
  "device_id": "uuid-v4"
}
```

---

### 5. Enviar Respostas em Lote (Sincronização Offline)

```
POST /mobile/v1/answer-sheets/manual-entry/batch
Authorization: Bearer <token>
X-Device-Id: <uuid-v4>
Content-Type: application/json

{
  "submissions": [
    {
      "offline_submission_id": "local-uuid-1",
      "gabarito_id": "uuid",
      "student_id": "uuid",
      "answers": {"1": "A", "2": "B"},
      "device_id": "uuid-v4"
    },
    {
      "offline_submission_id": "local-uuid-2",
      "gabarito_id": "uuid",
      "student_id": "uuid2",
      "answers": {"1": "C", "2": "D"},
      "device_id": "uuid-v4"
    }
  ]
}
```

**Resposta:**
```json
{
  "results": [
    {
      "offline_submission_id": "local-uuid-1",
      "status": "applied",
      "message": "Respostas registradas com sucesso",
      "data": {...}
    },
    {
      "offline_submission_id": "local-uuid-2",
      "status": "applied",
      "message": "Respostas registradas com sucesso",
      "data": {...}
    }
  ]
}
```

## Fluxo de Uso

### 1. Download Inicial (Online)

```
1. App abre → Professor faz login
2. Seleciona escola → Baixa bundle
3. Bundle inclui:
   - Avaliações online (testes com questões)
   - Gabaritos de cartões (só estrutura)
   - Lista de alunos
```

### 2. Uso Offline

```
Professor pode:
- Responder avaliações online pelos alunos
- Marcar respostas dos cartões físicos
  
Para cada cartão:
1. Seleciona gabarito
2. Seleciona aluno
3. Marca respostas (A, B, C, D, em branco, inválida)
4. Salva localmente
```

### 3. Sincronização (Online)

```
1. App detecta conexão
2. Envia respostas em lote:
   - Avaliações online → /mobile/v1/sync/upload
   - Cartões resposta → /mobile/v1/answer-sheets/manual-entry/batch
3. Backend processa e retorna resultados
```

## Permissões

| Role | Pode Baixar | Pode Marcar Respostas |
|------|-------------|----------------------|
| Admin | Todos os gabaritos | Todos os alunos |
| Aplicador | Todos os gabaritos | Todos os alunos |
| Professor | Gabaritos que criou | Alunos das turmas vinculadas |
| Coordenador | Todos os gabaritos | Todos os alunos |
| Diretor | Todos os gabaritos | Todos os alunos |

## Arquivos Modificados

### Novos Arquivos
- `app/services/mobile/answer_sheet_mobile_service.py`
  - Serialização de gabaritos
  - Coleta de gabaritos por escola
  
- `app/routes/mobile/answer_sheet_routes.py`
  - Rotas mobile para entrada manual
  - Endpoints de listagem e submissão

### Arquivos Modificados
- `app/services/mobile/bundle_service.py`
  - `collect_school_scope()`: agora retorna gabaritos
  - `build_bundle_response()`: inclui gabaritos no payload
  
- `app/services/mobile/offline_pack_service.py`
  - `collect_filtered_scope()`: coleta gabaritos filtrados
  - `redeem_offline_pack_page()`: inclui gabaritos no pacote
  
- `app/routes/mobile/__init__.py`
  - Import das novas rotas

## Serviços Reutilizados

O sistema mobile reutiliza completamente os serviços existentes de entrada manual:

- `app/services/cartao_resposta/manual_answer_sheet_service.py`
  - `get_manual_entry_form()`: formulário de entrada
  - `submit_manual_correction()`: processamento de respostas
  - `list_students_for_gabarito()`: listagem de alunos

- `app/services/cartao_resposta/correction_new_grid.py`
  - `AnswerSheetCorrectionNewGrid._build_result()`: cálculo de nota
  - `AnswerSheetCorrectionNewGrid.salvar_resultado()`: persistência

## Próximos Passos (Futuro)

1. **Leitura por Câmera**
   - Adicionar endpoint mobile para upload de foto do cartão
   - Reutilizar `correction_new_grid.py` para detecção OMR
   - Mesmo fluxo de salvamento

2. **Sincronização Incremental**
   - Enviar apenas respostas novas/modificadas
   - Controle de versão por gabarito

3. **Validação Offline**
   - Calcular nota localmente no app
   - Mostrar feedback imediato ao professor

## Testes

### Teste Manual do Bundle

```bash
curl -X GET "http://localhost:5000/mobile/v1/sync/bundle?school_id=<uuid>&page=1" \
  -H "Authorization: Bearer <token>" \
  -H "X-Device-Id: $(uuidgen)" \
  -H "X-City-Context: <city-slug>"
```

Verificar resposta contém:
- `answer_sheet_gabaritos`: objeto com gabaritos
- `student_gabarito_links`: array de vínculos

### Teste de Entrada Manual

```bash
curl -X POST "http://localhost:5000/mobile/v1/answer-sheets/manual-entry/submit" \
  -H "Authorization: Bearer <token>" \
  -H "X-Device-Id: $(uuidgen)" \
  -H "X-City-Context: <city-slug>" \
  -H "Content-Type: application/json" \
  -d '{
    "gabarito_id": "<uuid>",
    "student_id": "<uuid>",
    "answers": {"1": "A", "2": "B", "3": null}
  }'
```

Verificar resposta contém:
- `correct`, `wrong`, `blank`, `total`
- `score`, `proficiency`
- `detection_method: "manual"`
