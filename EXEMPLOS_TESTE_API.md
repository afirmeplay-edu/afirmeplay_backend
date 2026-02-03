# 🧪 Exemplos de Testes da API - Cartões Resposta

## 📋 Cenários de Teste

### **1. TESTE BÁSICO - Uma Turma**

```http
POST http://localhost:5000/answer-sheets/generate
Authorization: Bearer {seu_token_jwt}
Content-Type: application/json

{
  "class_id": "62ce579a-d20c-4823-a706-ebd6ef9a1987",
  "num_questions": 8,
  "use_blocks": true,
  "blocks_config": {
    "use_blocks": true,
    "num_blocks": 2,
    "blocks": [
      {
        "block_id": 1,
        "subject_name": "Português",
        "questions_count": 4,
        "start_question": 1,
        "end_question": 4
      },
      {
        "block_id": 2,
        "subject_name": "Matemática",
        "questions_count": 4,
        "start_question": 5,
        "end_question": 8
      }
    ]
  },
  "correct_answers": {
    "1": "B", "2": "B", "3": "B", "4": "B",
    "5": "B", "6": "B", "7": "B", "8": "B"
  },
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C", "D"],
    "4": ["A", "B", "C", "D"],
    "5": ["A", "B", "C", "D"],
    "6": ["A", "B", "C", "D"],
    "7": ["A", "B", "C", "D"],
    "8": ["A", "B", "C", "D"]
  },
  "test_data": {
    "title": "Avaliação Teste",
    "municipality": "Jaru",
    "state": "Rondônia",
    "grade_name": "6º Ano"
  }
}
```

**Resposta Esperada:**

```json
{
	"status": "processing",
	"message": "Cartões de resposta sendo gerados em background (class: Turma A). Use o task_id para verificar o status.",
	"task_id": "abc-123-xyz",
	"scope": "class",
	"scope_name": "Turma A",
	"batch_id": null,
	"gabarito_ids": ["d2edfd82-5d0b-471a-9cec-829b81270b2e"],
	"classes_count": 1,
	"classes": [
		{
			"class_id": "62ce579a-d20c-4823-a706-ebd6ef9a1987",
			"class_name": "Turma A",
			"gabarito_id": "d2edfd82-5d0b-471a-9cec-829b81270b2e",
			"grade_name": "6º Ano"
		}
	],
	"num_questions": 8,
	"polling_url": "/answer-sheets/task/abc-123-xyz/status"
}
```

---

### **2. TESTE - Todas Turmas de Uma Série**

```http
POST http://localhost:5000/answer-sheets/generate
Authorization: Bearer {seu_token_jwt}
Content-Type: application/json

{
  "grade_id": "uuid-da-serie-6-ano",
  "school_id": "56bfd6b8-8465-4331-a13b-06cb06a8516d",
  "num_questions": 8,
  "use_blocks": true,
  "blocks_config": {
    "use_blocks": true,
    "num_blocks": 2,
    "blocks": [
      {
        "block_id": 1,
        "subject_name": "Português",
        "questions_count": 4,
        "start_question": 1,
        "end_question": 4
      },
      {
        "block_id": 2,
        "subject_name": "Matemática",
        "questions_count": 4,
        "start_question": 5,
        "end_question": 8
      }
    ]
  },
  "correct_answers": {
    "1": "B", "2": "B", "3": "B", "4": "B",
    "5": "B", "6": "B", "7": "B", "8": "B"
  },
  "test_data": {
    "title": "Avaliação Série Completa",
    "municipality": "Jaru",
    "state": "Rondônia",
    "grade_name": "6º Ano"
  }
}
```

**Resposta Esperada:**

```json
{
	"status": "processing",
	"message": "Cartões de resposta sendo gerados em background (grade: Série 6º Ano). Use o task_id para verificar o status.",
	"task_id": "def-456-xyz",
	"scope": "grade",
	"scope_name": "Série 6º Ano",
	"batch_id": "batch-uuid-123",
	"gabarito_ids": ["gab-1", "gab-2", "gab-3"],
	"classes_count": 3,
	"classes": [
		{
			"class_id": "class-1",
			"class_name": "Turma A",
			"gabarito_id": "gab-1",
			"grade_name": "6º Ano"
		},
		{
			"class_id": "class-2",
			"class_name": "Turma B",
			"gabarito_id": "gab-2",
			"grade_name": "6º Ano"
		},
		{
			"class_id": "class-3",
			"class_name": "Turma C",
			"gabarito_id": "gab-3",
			"grade_name": "6º Ano"
		}
	],
	"num_questions": 8,
	"polling_url": "/answer-sheets/task/def-456-xyz/status"
}
```

---

### **3. TESTE - Escola Inteira**

```http
POST http://localhost:5000/answer-sheets/generate
Authorization: Bearer {seu_token_jwt}
Content-Type: application/json

{
  "school_id": "56bfd6b8-8465-4331-a13b-06cb06a8516d",
  "num_questions": 8,
  "use_blocks": true,
  "blocks_config": {
    "use_blocks": true,
    "num_blocks": 2,
    "blocks": [
      {
        "block_id": 1,
        "subject_name": "Português",
        "questions_count": 4,
        "start_question": 1,
        "end_question": 4
      },
      {
        "block_id": 2,
        "subject_name": "Matemática",
        "questions_count": 4,
        "start_question": 5,
        "end_question": 8
      }
    ]
  },
  "correct_answers": {
    "1": "B", "2": "B", "3": "B", "4": "B",
    "5": "B", "6": "B", "7": "B", "8": "B"
  },
  "test_data": {
    "title": "Avaliação Escola Completa",
    "municipality": "Jaru",
    "state": "Rondônia"
  }
}
```

**Resposta Esperada:**

```json
{
	"status": "processing",
	"message": "Cartões de resposta sendo gerados em background (school: Escola Municipal). Use o task_id para verificar o status.",
	"task_id": "ghi-789-xyz",
	"scope": "school",
	"scope_name": "Escola Municipal",
	"batch_id": "batch-uuid-456",
	"gabarito_ids": [
		"gab-1",
		"gab-2",
		"gab-3",
		"gab-4",
		"gab-5",
		"gab-6",
		"gab-7",
		"gab-8"
	],
	"classes_count": 8,
	"classes": [
		{
			"class_id": "class-1",
			"class_name": "Turma A",
			"gabarito_id": "gab-1",
			"grade_name": "6º Ano"
		},
		{
			"class_id": "class-2",
			"class_name": "Turma B",
			"gabarito_id": "gab-2",
			"grade_name": "6º Ano"
		},
		{
			"class_id": "class-3",
			"class_name": "Turma A",
			"gabarito_id": "gab-3",
			"grade_name": "7º Ano"
		}
		// ... mais turmas
	],
	"num_questions": 8,
	"polling_url": "/answer-sheets/task/ghi-789-xyz/status"
}
```

---

## 🔍 Verificar Status da Task

```http
GET http://localhost:5000/answer-sheets/task/abc-123-xyz/status
Authorization: Bearer {seu_token_jwt}
```

**Resposta (Processando):**

```json
{
	"status": "processing",
	"message": "Cartões sendo gerados...",
	"task_id": "abc-123-xyz"
}
```

**Resposta (Concluído):**

```json
{
	"status": "completed",
	"message": "Cartões gerados com sucesso",
	"task_id": "abc-123-xyz",
	"result": {
		"success": true,
		"scope": "school",
		"batch_id": "batch-uuid-456",
		"gabarito_ids": [
			"gab-1",
			"gab-2",
			"gab-3",
			"gab-4",
			"gab-5",
			"gab-6",
			"gab-7",
			"gab-8"
		],
		"num_questions": 8,
		"total_classes": 8,
		"total_students": 240,
		"total_pdfs": 8,
		"minio_url": "https://minio.example.com/answer-sheets/gabaritos/batch/batch-uuid-456/cartoes.zip",
		"download_size_bytes": 15728640,
		"classes": [
			{
				"gabarito_id": "gab-1",
				"class_id": "class-1",
				"class_name": "Turma A",
				"grade_name": "6º Ano",
				"filename": "6º Ano - Turma A.pdf",
				"total_students": 30,
				"total_pages": 30
			},
			{
				"gabarito_id": "gab-2",
				"class_id": "class-2",
				"class_name": "Turma B",
				"grade_name": "6º Ano",
				"filename": "6º Ano - Turma B.pdf",
				"total_students": 28,
				"total_pages": 28
			}
			// ... mais turmas
		]
	}
}
```

---

## 📥 Download do ZIP

### **Download Individual (Gabarito)**

```http
GET http://localhost:5000/answer-sheets/gabarito/gab-1/download
Authorization: Bearer {seu_token_jwt}
```

**Resposta:**

```json
{
	"download_url": "https://minio.example.com/presigned-url-expires-1h",
	"expires_in": "1 hour",
	"gabarito_id": "gab-1",
	"test_id": null,
	"class_id": "class-1",
	"class_name": "Turma A",
	"title": "Avaliação Escola Completa",
	"num_questions": 8,
	"generated_at": "2026-02-03T18:30:00",
	"created_at": "2026-02-03T18:25:00",
	"minio_url": "https://minio.example.com/answer-sheets/gabaritos/batch/batch-uuid-456/cartoes.zip",
	"is_batch": true,
	"batch_id": "batch-uuid-456"
}
```

### **Download de Batch Completo**

```http
GET http://localhost:5000/answer-sheets/batch/batch-uuid-456/download
Authorization: Bearer {seu_token_jwt}
```

**Resposta:**

```json
{
	"download_url": "https://minio.example.com/presigned-url-expires-1h",
	"expires_in": "1 hour",
	"batch_id": "batch-uuid-456",
	"classes_count": 8,
	"classes": [
		{
			"gabarito_id": "gab-1",
			"class_id": "class-1",
			"class_name": "Turma A",
			"grade_name": "6º Ano",
			"school_name": "Escola Municipal"
		},
		{
			"gabarito_id": "gab-2",
			"class_id": "class-2",
			"class_name": "Turma B",
			"grade_name": "6º Ano",
			"school_name": "Escola Municipal"
		}
		// ... mais turmas
	],
	"title": "Avaliação Escola Completa",
	"num_questions": 8,
	"generated_at": "2026-02-03T18:30:00",
	"created_at": "2026-02-03T18:25:00",
	"minio_url": "https://minio.example.com/answer-sheets/gabaritos/batch/batch-uuid-456/cartoes.zip"
}
```

---

## 🧪 Scripts de Teste com cURL

### **Teste 1: Uma Turma**

```bash
curl -X POST http://localhost:5000/answer-sheets/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "class_id": "62ce579a-d20c-4823-a706-ebd6ef9a1987",
    "num_questions": 8,
    "use_blocks": true,
    "blocks_config": {
      "use_blocks": true,
      "blocks": [
        {"block_id": 1, "subject_name": "Português", "start_question": 1, "end_question": 4, "questions_count": 4},
        {"block_id": 2, "subject_name": "Matemática", "start_question": 5, "end_question": 8, "questions_count": 4}
      ]
    },
    "correct_answers": {"1": "B", "2": "B", "3": "B", "4": "B", "5": "B", "6": "B", "7": "B", "8": "B"},
    "test_data": {
      "title": "Teste",
      "municipality": "Jaru",
      "state": "Rondônia"
    }
  }'
```

### **Teste 2: Verificar Status**

```bash
curl -X GET http://localhost:5000/answer-sheets/task/abc-123-xyz/status \
  -H "Authorization: Bearer $TOKEN"
```

### **Teste 3: Download**

```bash
curl -X GET http://localhost:5000/answer-sheets/gabarito/gab-1/download \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🐍 Scripts de Teste com Python

```python
import requests
import time

BASE_URL = "http://localhost:5000"
TOKEN = "seu_token_jwt_aqui"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. Gerar cartões para uma turma
payload = {
    "class_id": "62ce579a-d20c-4823-a706-ebd6ef9a1987",
    "num_questions": 8,
    "use_blocks": True,
    "blocks_config": {
        "use_blocks": True,
        "blocks": [
            {
                "block_id": 1,
                "subject_name": "Português",
                "start_question": 1,
                "end_question": 4,
                "questions_count": 4
            },
            {
                "block_id": 2,
                "subject_name": "Matemática",
                "start_question": 5,
                "end_question": 8,
                "questions_count": 4
            }
        ]
    },
    "correct_answers": {
        "1": "B", "2": "B", "3": "B", "4": "B",
        "5": "B", "6": "B", "7": "B", "8": "B"
    },
    "test_data": {
        "title": "Teste Python",
        "municipality": "Jaru",
        "state": "Rondônia"
    }
}

# Fazer request
response = requests.post(f"{BASE_URL}/answer-sheets/generate", json=payload, headers=headers)
data = response.json()

print(f"Status: {data['status']}")
print(f"Task ID: {data['task_id']}")
print(f"Scope: {data['scope']}")
print(f"Classes: {data['classes_count']}")

task_id = data['task_id']

# 2. Polling - aguardar conclusão
while True:
    time.sleep(5)  # Aguardar 5 segundos

    status_response = requests.get(f"{BASE_URL}/answer-sheets/task/{task_id}/status", headers=headers)
    status_data = status_response.json()

    print(f"Status atual: {status_data['status']}")

    if status_data['status'] == 'completed':
        print("✅ Geração concluída!")
        print(f"Total de PDFs: {status_data['result']['total_pdfs']}")
        print(f"Total de alunos: {status_data['result']['total_students']}")

        # 3. Fazer download
        if status_data['result'].get('batch_id'):
            download_url = f"{BASE_URL}/answer-sheets/batch/{status_data['result']['batch_id']}/download"
        else:
            gabarito_id = status_data['result']['gabarito_ids'][0]
            download_url = f"{BASE_URL}/answer-sheets/gabarito/{gabarito_id}/download"

        download_response = requests.get(download_url, headers=headers)
        download_data = download_response.json()

        print(f"📥 URL de download: {download_data['download_url']}")
        print(f"Expira em: {download_data['expires_in']}")

        break

    elif status_data['status'] == 'failed':
        print(f"❌ Erro: {status_data.get('error')}")
        break
```

---

## ✅ Checklist de Testes

- [ ] Gerar para 1 turma (escopo `class`)
- [ ] Gerar para série completa (escopo `grade`)
- [ ] Gerar para escola inteira (escopo `school`)
- [ ] Verificar polling de status
- [ ] Download individual de gabarito
- [ ] Download de batch completo
- [ ] Verificar estrutura do ZIP baixado
- [ ] Abrir PDF e verificar múltiplas páginas
- [ ] Verificar QR codes únicos em cada página
- [ ] Testar correção de cartão (QR code funciona)

---

## 🎯 Validações Importantes

1. **QR Code único por aluno**: Cada página deve ter QR diferente
2. **Nome do arquivo**: `Serie - Turma.pdf` (ex: `6º Ano - Turma A.pdf`)
3. **Estrutura ZIP**: Pastas por série se escopo for escola
4. **Blocos e alternativas**: Devem aparecer corretamente no PDF
5. **Dados do cabeçalho**: Nome do aluno, escola, turma, etc.
