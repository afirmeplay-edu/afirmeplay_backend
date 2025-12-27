# Documentação - Cartão Resposta

## Visão Geral

Sistema de geração e correção de cartões resposta usando detecção geométrica (triângulos de alinhamento e bolhas).

## Estrutura de Arquivos

```
app/
├── services/
│   └── cartao_resposta/
│       ├── __init__.py
│       ├── answer_sheet_generator.py    # Geração de PDFs
│       └── answer_sheet_correction.py    # Correção usando detecção geométrica
├── templates/
│   └── answer_sheet.html                # Template com triângulos de alinhamento
└── routes/
    └── answer_sheet_routes.py           # Rotas da API
```

## Rotas

### 1. POST `/answer-sheets/generate`

Gera cartões resposta em PDF para todos os alunos de uma turma e retorna como arquivo ZIP.

**Autenticação:** JWT Token obrigatório  
**Permissões:** admin, professor, coordenador, diretor, tecadm

#### Request Body

```json
{
	"class_id": "uuid-da-turma",
	"num_questions": 48,
	"use_blocks": true,
	"blocks_config": {
		"num_blocks": 4,
		"questions_per_block": 12,
		"separate_by_subject": false
	},
	"correct_answers": {
		"1": "A",
		"2": "B",
		"3": "C",
		"4": "D",
		"...": "..."
	},
	"test_data": {
		"title": "Avaliação de Matemática - 1º Bimestre",
		"municipality": "São Miguel dos Campos",
		"state": "ALAGOAS",
		"department": "Secretaria Municipal de Educação",
		"municipality_logo": "base64_encoded_logo (opcional)",
		"institution": "E.M.E.B João Paulo II",
		"grade_name": "5º Ano"
	},
	"test_id": "uuid-da-prova (opcional)"
}
```

#### Response (200 OK)

**Content-Type:** `application/zip`  
**Content-Disposition:** `attachment; filename="cartoes_resposta_TituloProva_gabaritoId.zip"`

O arquivo ZIP contém:

-   Todos os PDFs dos cartões resposta (um por aluno)
    -   Nome do arquivo: `cartao_NomeAluno_studentId.pdf`
-   Arquivo `metadata.json` com informações do gabarito:
    ```json
    {
      "gabarito_id": "uuid-do-gabarito",
      "test_id": "uuid-da-prova",
      "class_id": "uuid-da-turma",
      "title": "Avaliação de Matemática - 1º Bimestre",
      "num_questions": 48,
      "use_blocks": true,
      "blocks_config": {...},
      "generated_count": 25,
      "created_at": "2025-12-27T10:00:00"
    }
    ```

#### Response (400 Bad Request)

```json
{
	"error": "class_id é obrigatório"
}
```

#### Exemplo de Uso (cURL)

```bash
curl -X POST http://localhost:5000/answer-sheets/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_JWT_TOKEN" \
  -d '{
    "class_id": "123e4567-e89b-12d3-a456-426614174000",
    "num_questions": 48,
    "use_blocks": true,
    "blocks_config": {
      "num_blocks": 4,
      "questions_per_block": 12
    },
    "correct_answers": {
      "1": "A",
      "2": "B",
      "3": "C",
      "4": "D"
    },
    "test_data": {
      "title": "Avaliação de Matemática",
      "municipality": "São Miguel dos Campos",
      "state": "ALAGOAS"
    }
  }' \
  --output cartoes_resposta.zip
```

#### Exemplo de Uso (Python)

```python
import requests

response = requests.post(
    'http://localhost:5000/answer-sheets/generate',
    headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer SEU_JWT_TOKEN'
    },
    json={
        'class_id': '123e4567-e89b-12d3-a456-426614174000',
        'num_questions': 48,
        'use_blocks': True,
        'blocks_config': {
            'num_blocks': 4,
            'questions_per_block': 12
        },
        'correct_answers': {
            '1': 'A',
            '2': 'B',
            '3': 'C',
            '4': 'D'
        },
        'test_data': {
            'title': 'Avaliação de Matemática',
            'municipality': 'São Miguel dos Campos',
            'state': 'ALAGOAS'
        }
    }
)

if response.status_code == 200:
    # Salvar ZIP
    with open('cartoes_resposta.zip', 'wb') as f:
        f.write(response.content)
    print("✅ ZIP gerado com sucesso!")

    # Extrair metadata (opcional)
    import zipfile
    with zipfile.ZipFile('cartoes_resposta.zip', 'r') as zip_ref:
        metadata_json = zip_ref.read('metadata.json')
        import json
        metadata = json.loads(metadata_json)
        print(f"Gabarito ID: {metadata['gabarito_id']}")
        print(f"Total de cartões: {metadata['generated_count']}")
else:
    print(f"Erro: {response.json()}")
```

---

### 2. POST `/answer-sheets/correct`

Corrige um cartão resposta usando detecção geométrica (triângulos de alinhamento e bolhas).

**Autenticação:** JWT Token obrigatório  
**Permissões:** admin, professor, coordenador, diretor, tecadm

#### Request Body

```json
{
	"image": "base64_encoded_image_jpeg_ou_png",
	"gabarito_id": "uuid-do-gabarito (opcional, se não tiver test_id)",
	"test_id": "uuid-da-prova (opcional, se não tiver gabarito_id)"
}
```

**Nota:** É obrigatório fornecer `gabarito_id` OU `test_id`. O QR code no cartão também pode conter essas informações.

#### Response (200 OK)

```json
{
	"success": true,
	"student_id": "uuid-do-aluno",
	"gabarito_id": "uuid-do-gabarito",
	"test_id": "uuid-da-prova",
	"correct": 35,
	"total": 48,
	"percentage": 72.92,
	"answers": {
		"1": "A",
		"2": "B",
		"3": "C",
		"4": null,
		"...": "..."
	},
	"correction": {
		"total_questions": 48,
		"answered": 45,
		"correct": 35,
		"incorrect": 10,
		"unanswered": 3,
		"score_percentage": 72.92
	},
	"saved_answers": [
		{
			"question_number": 1,
			"question_id": "uuid-questao-1",
			"detected_answer": "A",
			"correct_answer": "A",
			"is_correct": true
		}
	],
	"detection_method": "geometric",
	"grade": 7.29,
	"proficiency": 72.92,
	"classification": "Proficiente",
	"evaluation_result_id": "uuid-resultado",
	"score_percentage": 72.92,
	"correct_answers": 35,
	"total_questions": 48
}
```

#### Response (400 Bad Request)

```json
{
	"success": false,
	"error": "QR Code não detectado ou inválido"
}
```

#### Exemplo de Uso (cURL)

```bash
curl -X POST http://localhost:5000/answer-sheets/correct \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer SEU_JWT_TOKEN" \
  -d '{
    "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    "gabarito_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

#### Exemplo de Uso (Python)

```python
import requests
import base64

# Ler imagem do arquivo
with open('cartao_resposta.jpg', 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

# Fazer requisição
response = requests.post(
    'http://localhost:5000/answer-sheets/correct',
    headers={
        'Content-Type': 'application/json',
        'Authorization': 'Bearer SEU_JWT_TOKEN'
    },
    json={
        'image': image_base64,
        'gabarito_id': '123e4567-e89b-12d3-a456-426614174000'
    }
)

result = response.json()
print(f"Aluno: {result['student_id']}")
print(f"Acertos: {result['correct']}/{result['total']}")
print(f"Nota: {result['grade']}")
```

---

### 3. GET `/answer-sheets/gabarito/<gabarito_id>`

Busca informações de um gabarito específico.

**Autenticação:** JWT Token obrigatório  
**Permissões:** admin, professor, coordenador, diretor, tecadm

#### Response (200 OK)

```json
{
	"id": "uuid-do-gabarito",
	"test_id": "uuid-da-prova",
	"class_id": "uuid-da-turma",
	"num_questions": 48,
	"use_blocks": true,
	"blocks_config": {
		"num_blocks": 4,
		"questions_per_block": 12,
		"separate_by_subject": false
	},
	"correct_answers": {
		"1": "A",
		"2": "B",
		"3": "C",
		"4": "D"
	},
	"title": "Avaliação de Matemática - 1º Bimestre",
	"created_at": "2025-12-27T10:00:00"
}
```

#### Response (404 Not Found)

```json
{
	"error": "Gabarito não encontrado"
}
```

#### Exemplo de Uso (cURL)

```bash
curl -X GET http://localhost:5000/answer-sheets/gabarito/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer SEU_JWT_TOKEN"
```

---

## Características do Cartão Resposta

### Marcadores Geométricos

O cartão resposta inclui **4 triângulos de alinhamento** nos cantos:

-   Canto superior esquerdo
-   Canto superior direito
-   Canto inferior esquerdo
-   Canto inferior direito

Esses triângulos são usados para:

1. Detectar a orientação do cartão
2. Corrigir perspectiva (desenho inclinado)
3. Fazer crop preciso da área de respostas

### Estrutura do Cartão

1. **Cabeçalho:**

    - Nome da prova
    - Dados do aluno (nome, escola, turma)
    - QR Code com metadados (student_id, test_id/gabarito_id)

2. **Instruções:**

    - Como preencher o cartão
    - Exemplos de marcação correta/incorreta

3. **Bloco do Aplicador:**

    - Campos para marcar ausências e necessidades especiais

4. **Grade de Respostas:**
    - Organizada em blocos (configurável)
    - Cada questão tem 4 alternativas (A, B, C, D)
    - Bolhas circulares para marcação

### Detecção de Respostas

O sistema usa **detecção geométrica** (não IA) para:

1. Detectar triângulos de alinhamento
2. Corrigir perspectiva da imagem
3. Fazer crop da área de respostas
4. Detectar bolhas marcadas usando:
    - Threshold binário invertido
    - Detecção de contornos circulares
    - Contagem de pixels preenchidos
    - Mapeamento por posição (A, B, C, D)

---

## Fluxo de Uso

### 1. Geração de Cartões

```python
import requests
import zipfile
import json

# 1. Preparar dados
data = {
    "class_id": "uuid-turma",
    "num_questions": 48,
    "use_blocks": True,
    "blocks_config": {
        "num_blocks": 4,
        "questions_per_block": 12
    },
    "correct_answers": {
        "1": "A", "2": "B", ...
    },
    "test_data": {
        "title": "Avaliação",
        "municipality": "...",
        "state": "..."
    }
}

# 2. Gerar cartões (retorna ZIP)
response = requests.post('/answer-sheets/generate', json=data)

if response.status_code == 200:
    # 3. Salvar ZIP
    with open('cartoes_resposta.zip', 'wb') as f:
        f.write(response.content)

    # 4. Extrair PDFs do ZIP (opcional)
    with zipfile.ZipFile('cartoes_resposta.zip', 'r') as zip_ref:
        # Ler metadata
        metadata_json = zip_ref.read('metadata.json')
        metadata = json.loads(metadata_json)
        gabarito_id = metadata['gabarito_id']

        # Extrair todos os PDFs
        zip_ref.extractall('cartoes_extraidos/')

    print(f"✅ {metadata['generated_count']} cartões gerados!")
    print(f"Gabarito ID: {gabarito_id}")
else:
    print(f"Erro: {response.json()}")
```

### 2. Correção de Cartões

```python
# 1. Ler imagem do cartão preenchido
with open('cartao_preenchido.jpg', 'rb') as f:
    image_data = f.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')

# 2. Enviar para correção
response = requests.post('/answer-sheets/correct', json={
    'image': image_base64,
    'gabarito_id': gabarito_id
})

# 3. Processar resultado
result = response.json()
if result['success']:
    print(f"Aluno: {result['student_id']}")
    print(f"Nota: {result['grade']}/10")
    print(f"Acertos: {result['correct']}/{result['total']}")
```

---

## Notas Importantes

1. **QR Code:** O QR code no cartão contém `student_id` e opcionalmente `test_id` ou `gabarito_id`. Isso permite identificar o aluno automaticamente.

2. **Gabarito:** O gabarito pode ser vinculado a uma prova (`test_id`) ou ser independente (`gabarito_id`). Se tiver `test_id`, as respostas são salvas no banco e calcula-se proficiência/classificação.

3. **Detecção Geométrica:** O sistema não usa IA, mas sim algoritmos de visão computacional (OpenCV) para detectar triângulos e bolhas. Isso é mais rápido e não requer API externa.

4. **Template:** O template `answer_sheet.html` foi atualizado para incluir triângulos de alinhamento nos 4 cantos, seguindo o padrão do `institutional_test_hybrid.html`.

---

## Troubleshooting

### Erro: "QR Code não detectado"

-   Verifique se a imagem está nítida
-   Certifique-se de que o QR code está visível e não está danificado
-   Tente aumentar a resolução da imagem

### Erro: "Triângulos de alinhamento não detectados"

-   Verifique se a imagem capturou os 4 cantos do cartão
-   Certifique-se de que os triângulos estão visíveis (não cortados)
-   Tente melhorar a iluminação da foto

### Erro: "Nenhuma bolha detectada"

-   Verifique se as bolhas foram preenchidas completamente
-   Certifique-se de que a caneta usada é preta
-   Verifique se a imagem está focada e nítida

---

## Changelog

### 2025-12-27

-   ✅ Reorganização: arquivos movidos para `app/services/cartao_resposta/`
-   ✅ Template atualizado: uso de triângulos de alinhamento (híbrido)
-   ✅ Correção atualizada: uso de `correcao_hybrid.py` ao invés de `correcaoIA.py`
-   ✅ Detecção geométrica: substituição de IA por algoritmos OpenCV
-   ✅ **POST /answer-sheets/generate agora retorna ZIP** ao invés de JSON com base64
    -   Melhor performance para turmas grandes (30+ alunos)
    -   ZIP contém todos os PDFs + arquivo metadata.json
    -   Nome do arquivo: `cartoes_resposta_TituloProva_gabaritoId.zip`
