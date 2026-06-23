# 🎯 Exemplo de Contrato - GET Gabarito

## Request

```http
GET /answer-sheets/gabarito/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
X-City-Context: city-uuid-123
```

---

## Response (200 OK)

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Provinha Brasil - 1º Bimestre",
  "num_questions": 30,
  "use_blocks": true,
  "correct_answers": {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "A",
    ...
    "30": "B"
  },
  "created_at": "2026-06-20T10:30:00.000Z",
  "latest_generation_job_id": "job-uuid-456",
  "generations_count": 1,
  
  "blocks_config": {
    "use_blocks": true,
    "num_blocks": 2,
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "e3b0c442-98fc-1c14-b39f-92d1282148ab",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      },
      {
        "block_id": 2,
        "subject_id": "d8b5e345-45a6-4b2c-8f9d-123456789abc",
        "subject_name": "Língua Portuguesa",
        "start_question": 16,
        "end_question": 30,
        "questions_count": 15
      }
    ],
    "topology": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "e3b0c442-98fc-1c14-b39f-92d1282148ab",
          "subject_name": "Matemática",
          "questions": [
            {
              "q": 1,
              "alternatives": ["A", "B", "C", "D"],
              "skills": [
                "a1b2c3d4-1234-5678-90ab-cdef12345678",
                "b2c3d4e5-2345-6789-01bc-def123456789"
              ]
            },
            {
              "q": 2,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["c3d4e5f6-3456-7890-12cd-ef1234567890"]
            },
            {
              "q": 3,
              "alternatives": ["A", "B", "C", "D"],
              "skills": []
            }
            // ... questões 4-15
          ]
        },
        {
          "block_id": 2,
          "subject_id": "d8b5e345-45a6-4b2c-8f9d-123456789abc",
          "subject_name": "Língua Portuguesa",
          "questions": [
            {
              "q": 16,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["d4e5f6a7-4567-8901-23de-f12345678901"]
            }
            // ... questões 17-30
          ]
        }
      ]
    }
  },
  
  "generations": [
    {
      "job_id": "job-uuid-456",
      "created_at": "2026-06-20T10:45:00.000Z",
      "total_students_generated": 150,
      "classes_generated": 5
    }
  ],
  
  "question_skills": {
    "1": [
      "a1b2c3d4-1234-5678-90ab-cdef12345678",
      "b2c3d4e5-2345-6789-01bc-def123456789"
    ],
    "2": ["c3d4e5f6-3456-7890-12cd-ef1234567890"],
    "3": [],
    "4": ["e5f6a7b8-5678-9012-34ef-123456789012"],
    "5": [],
    "6": ["f6a7b8c9-6789-0123-45f0-123456789012"],
    "7": [],
    "8": [],
    "9": ["a7b8c9d0-7890-1234-5601-234567890123"],
    "10": [],
    "11": ["b8c9d0e1-8901-2345-6712-345678901234"],
    "12": [],
    "13": [],
    "14": ["c9d0e1f2-9012-3456-7823-456789012345"],
    "15": [],
    "16": ["d4e5f6a7-4567-8901-23de-f12345678901"],
    "17": ["e5f6a7b8-5678-9012-34ef-012345678901"],
    "18": [],
    "19": ["f6a7b8c9-6789-0123-45f0-123456789012"],
    "20": [],
    "21": [],
    "22": ["a7b8c9d0-7890-1234-5601-234567890123"],
    "23": [],
    "24": [],
    "25": ["b8c9d0e1-8901-2345-6712-345678901234"],
    "26": [],
    "27": [],
    "28": ["c9d0e1f2-9012-3456-7823-456789012345"],
    "29": [],
    "30": ["d0e1f2a3-0123-4567-8934-567890123456"]
  },
  
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C", "D"],
    "4": ["A", "B", "C", "D"],
    "5": ["A", "B", "C", "D"],
    "6": ["A", "B", "C", "D"],
    "7": ["A", "B", "C", "D"],
    "8": ["A", "B", "C", "D"],
    "9": ["A", "B", "C", "D"],
    "10": ["A", "B", "C", "D"],
    "11": ["A", "B", "C", "D"],
    "12": ["A", "B", "C", "D"],
    "13": ["A", "B", "C", "D"],
    "14": ["A", "B", "C", "D"],
    "15": ["A", "B", "C", "D"],
    "16": ["A", "B", "C", "D"],
    "17": ["A", "B", "C", "D"],
    "18": ["A", "B", "C", "D"],
    "19": ["A", "B", "C", "D"],
    "20": ["A", "B", "C", "D"],
    "21": ["A", "B", "C", "D"],
    "22": ["A", "B", "C", "D"],
    "23": ["A", "B", "C", "D"],
    "24": ["A", "B", "C", "D"],
    "25": ["A", "B", "C", "D"],
    "26": ["A", "B", "C", "D"],
    "27": ["A", "B", "C", "D"],
    "28": ["A", "B", "C", "D"],
    "29": ["A", "B", "C", "D"],
    "30": ["A", "B", "C", "D"]
  },
  
  "skill_codes": {
    "a1b2c3d4-1234-5678-90ab-cdef12345678": "EF05MA01",
    "b2c3d4e5-2345-6789-01bc-def123456789": "EF05MA02",
    "c3d4e5f6-3456-7890-12cd-ef1234567890": "EF05MA03",
    "e5f6a7b8-5678-9012-34ef-123456789012": "EF05MA04",
    "f6a7b8c9-6789-0123-45f0-123456789012": "EF05MA05",
    "a7b8c9d0-7890-1234-5601-234567890123": "EF05MA06",
    "b8c9d0e1-8901-2345-6712-345678901234": "EF05MA07",
    "c9d0e1f2-9012-3456-7823-456789012345": "EF05MA08",
    "d4e5f6a7-4567-8901-23de-f12345678901": "EF05LP01",
    "e5f6a7b8-5678-9012-34ef-012345678901": "EF05LP02",
    "f6a7b8c9-6789-0123-45f0-123456789012": "EF05LP03",
    "a7b8c9d0-7890-1234-5601-234567890123": "EF05LP04",
    "b8c9d0e1-8901-2345-6712-345678901234": "EF05LP05",
    "c9d0e1f2-9012-3456-7823-456789012345": "EF05LP06",
    "d0e1f2a3-0123-4567-8934-567890123456": "EF05LP07"
  }
}
```

---

## 📊 Interpretação dos Dados

### Alternativas (Global)
Todas as questões usam `["A", "B", "C", "D"]`
→ **Frontend marca:** ✅ "Usar as mesmas alternativas em todas as questões"

### Habilidades

| Questão | Habilidades | Exibir |
|---------|------------|--------|
| Q1 | 2 | ✅ EF05MA01, EF05MA02 |
| Q2 | 1 | ✅ EF05MA03 |
| Q3 | 0 | ❌ Sem habilidades |
| Q4 | 1 | ✅ EF05MA04 |
| Q5 | 0 | ❌ Sem habilidades |
| ... | ... | ... |
| Q16 | 1 | ✅ EF05LP01 |
| Q30 | 1 | ✅ EF05LP07 |

### Blocos

- **Bloco 1:** Matemática (Q1-Q15) - 8 habilidades
- **Bloco 2:** Português (Q16-Q30) - 7 habilidades

---

## 💻 Código Frontend (React/TypeScript)

```typescript
interface GabaritoData {
  id: string;
  title: string;
  num_questions: number;
  question_skills: Record<string, string[]>;
  questions_options: Record<string, string[]>;
  skill_codes: Record<string, string>;
}

function GabaritoSummary({ data }: { data: GabaritoData }) {
  // Detectar se usa alternativas globais
  const allOptions = Object.values(data.questions_options);
  const firstOption = JSON.stringify(allOptions[0]?.sort());
  const isGlobal = allOptions.every(opt => 
    JSON.stringify(opt.sort()) === firstOption
  );
  
  return (
    <div>
      <h2>{data.title}</h2>
      <p>Total de questões: {data.num_questions}</p>
      
      {/* Alternativas */}
      <div>
        <h3>Alternativas</h3>
        {isGlobal ? (
          <p>✅ Global: {allOptions[0]?.join(', ')}</p>
        ) : (
          <p>❌ Individuais por questão</p>
        )}
      </div>
      
      {/* Habilidades */}
      <div>
        <h3>Habilidades por Questão</h3>
        {Object.entries(data.question_skills).map(([qNum, uuids]) => {
          if (uuids.length === 0) return null;
          
          const codes = uuids.map(uuid => data.skill_codes[uuid]).join(', ');
          return (
            <div key={qNum}>
              <strong>Q{qNum}:</strong> {codes}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

---

## ✅ Checklist de Uso

- [x] Request com `Authorization` e `X-City-Context`
- [x] Receber `question_skills` (mapa achatado)
- [x] Receber `questions_options` (mapa achatado)
- [x] Receber `skill_codes` (códigos BNCC)
- [x] Detectar alternativas globais vs individuais
- [x] Exibir habilidades com códigos legíveis
- [x] Carregar estado inicial do formulário de edição
