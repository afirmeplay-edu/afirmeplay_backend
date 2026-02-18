# 📚 Exemplos de Uso - Rotas de Realocação de Turmas e Alunos

## 🎯 Índice

1. [Realocação de Turma](#1-realocação-de-turma)
2. [Mudança de Aluno de Turma](#2-mudança-de-aluno-de-turma)
3. [Adicionar Aluno à Turma](#3-adicionar-aluno-à-turma)
4. [Remover Aluno da Turma](#4-remover-aluno-da-turma)

---

## 1. Realocação de Turma

### 🔄 Mover Turma para Outra Escola

**Endpoint:** `PUT /classes/{class_id}`

**Descrição:** Move uma turma completa para outra escola do mesmo município. Atualiza automaticamente todos os alunos da turma.

**Funcionalidades:**

- ✅ Valida que escola destino é do mesmo município
- ✅ Renomeia automaticamente se houver conflito de nome
- ✅ Atualiza todos os alunos da turma (school_id e city_id)

### Exemplo 1: Realocação Simples (Sem Conflito de Nome)

**Request:**

```http
PUT /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4
Authorization: Bearer {token}
Content-Type: application/json

{
  "school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57"
}
```

**Response:** `200 OK`

```json
{
	"message": "Turma atualizada com sucesso",
	"class": {
		"id": "a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4",
		"name": "5º Ano A",
		"school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"school_changed": true,
		"name_changed": false,
		"students_updated": 25
	},
	"relocation": {
		"old_school_id": "ee19486a-0d27-466d-97eb-aab782d993d5",
		"new_school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"students_moved": [
			{
				"id": "e56ef919-cd6d-43f6-a737-181c6ef598d6",
				"name": "João Silva",
				"old_school": "ee19486a-0d27-466d-97eb-aab782d993d5",
				"new_school": "396c651f-82ee-4b7d-b3ec-35442d1b1b57"
			}
			// ... mais 24 alunos
		]
	}
}
```

### Exemplo 2: Realocação com Renomeação Automática

**Cenário:** Escola destino já tem uma turma "5º Ano A"

**Request:**

```http
PUT /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4
Authorization: Bearer {token}
Content-Type: application/json

{
  "school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57"
}
```

**Response:** `200 OK`

```json
{
	"message": "Turma atualizada com sucesso",
	"class": {
		"id": "a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4",
		"name": "5º Ano A (2)",
		"school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"school_changed": true,
		"name_changed": true,
		"students_updated": 25
	},
	"relocation": {
		"old_school_id": "ee19486a-0d27-466d-97eb-aab782d993d5",
		"new_school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"students_moved": [
			{
				"id": "e56ef919-cd6d-43f6-a737-181c6ef598d6",
				"name": "João Silva",
				"old_school": "ee19486a-0d27-466d-97eb-aab782d993d5",
				"new_school": "396c651f-82ee-4b7d-b3ec-35442d1b1b57"
			}
			// ... mais alunos
		]
	},
	"auto_renamed": {
		"old_name": "5º Ano A",
		"new_name": "5º Ano A (2)",
		"reason": "Nome duplicado na escola destino"
	}
}
```

### Exemplo 3: Erro - Município Diferente

**Request:**

```http
PUT /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4
Authorization: Bearer {token}
Content-Type: application/json

{
  "school_id": "xyz-escola-outro-municipio"
}
```

**Response:** `400 Bad Request`

```json
{
	"error": "Realocação não permitida",
	"details": "A turma não pode ser movida para escola de município diferente. Escola atual: city-123, Escola destino: city-456"
}
```

### Exemplo 4: Renomear Turma (Sem Mover)

**Request:**

```http
PUT /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "5º Ano B"
}
```

**Response:** `200 OK` ou `400 Bad Request` se já existir

```json
{
	"message": "Turma atualizada com sucesso",
	"class": {
		"id": "a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4",
		"name": "5º Ano B",
		"school_id": "ee19486a-0d27-466d-97eb-aab782d993d5",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"school_changed": false,
		"name_changed": true,
		"students_updated": 0
	}
}
```

---

## 2. Mudança de Aluno de Turma

### 🔄 Mover Aluno para Outra Turma

**Endpoint:** `PUT /students/{student_id}/{class_id}`

**Descrição:** Move um aluno para outra turma. Se a nova turma for de outra escola, atualiza automaticamente a escola e cidade do aluno.

**Funcionalidades:**

- ✅ Permite mudar aluno para turma de outra escola
- ✅ Atualiza automaticamente school_id
- ✅ Atualiza automaticamente city_id do usuário

### Exemplo 1: Mudança de Turma (Mesma Escola)

**Request:**

```http
PUT /students/e56ef919-cd6d-43f6-a737-181c6ef598d6/bcdba5f2-a193-4562-a44c-3cb077266b03
Authorization: Bearer {token}
Content-Type: application/json

{
  "class_id": "957e3216-9220-4e55-8904-d21689825e95"
}
```

**Response:** `200 OK`

```json
{
	"message": "Aluno atualizado com sucesso",
	"student": {
		"id": "e56ef919-cd6d-43f6-a737-181c6ef598d6",
		"name": "João Silva",
		"email": "joao.silva@escola.com",
		"class_id": "957e3216-9220-4e55-8904-d21689825e95",
		"school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"class_changed": true,
		"school_changed": false
	},
	"relocation": {
		"old_class_id": "bcdba5f2-a193-4562-a44c-3cb077266b03",
		"new_class_id": "957e3216-9220-4e55-8904-d21689825e95",
		"old_school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"new_school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"city_updated": false
	}
}
```

### Exemplo 2: Mudança de Turma (Escola Diferente)

**Request:**

```http
PUT /students/e56ef919-cd6d-43f6-a737-181c6ef598d6/bcdba5f2-a193-4562-a44c-3cb077266b03
Authorization: Bearer {token}
Content-Type: application/json

{
  "class_id": "abc12345-1234-1234-1234-123456789abc"
}
```

**Response:** `200 OK`

```json
{
	"message": "Aluno atualizado com sucesso",
	"student": {
		"id": "e56ef919-cd6d-43f6-a737-181c6ef598d6",
		"name": "João Silva",
		"email": "joao.silva@escola.com",
		"class_id": "abc12345-1234-1234-1234-123456789abc",
		"school_id": "nova-escola-123",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"class_changed": true,
		"school_changed": true
	},
	"relocation": {
		"old_class_id": "bcdba5f2-a193-4562-a44c-3cb077266b03",
		"new_class_id": "abc12345-1234-1234-1234-123456789abc",
		"old_school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"new_school_id": "nova-escola-123",
		"city_updated": true
	}
}
```

### Exemplo 3: Atualizar Dados do Aluno

**Request:**

```http
PUT /students/e56ef919-cd6d-43f6-a737-181c6ef598d6/bcdba5f2-a193-4562-a44c-3cb077266b03
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "João Pedro Silva",
  "email": "joao.pedro@escola.com",
  "birth_date": "2010-05-15"
}
```

**Response:** `200 OK`

```json
{
	"message": "Aluno atualizado com sucesso",
	"student": {
		"id": "e56ef919-cd6d-43f6-a737-181c6ef598d6",
		"name": "João Pedro Silva",
		"email": "joao.pedro@escola.com",
		"class_id": "bcdba5f2-a193-4562-a44c-3cb077266b03",
		"school_id": "396c651f-82ee-4b7d-b3ec-35442d1b1b57",
		"grade_id": "b93e5e89-123a-4567-8901-234567890abc"
	},
	"changes": {
		"class_changed": false,
		"school_changed": false
	}
}
```

---

## 3. Adicionar Aluno à Turma

### ➕ Vincular Aluno a uma Turma

**Endpoint:** `POST /classes/{class_id}/add_student`

**Descrição:** Adiciona um ou mais alunos a uma turma. Atualiza automaticamente school_id e city_id.

### Exemplo 1: Adicionar Um Aluno

**Request:**

```http
POST /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4/add_student
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "5a2fd1c6-44ad-4033-8eb2-3eca8b924838"
}
```

**Response:** `200 OK`

```json
{
	"message": "Students processed for class a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4",
	"added_students": ["5a2fd1c6-44ad-4033-8eb2-3eca8b924838"],
	"total_added": 1,
	"errors": null
}
```

### Exemplo 2: Adicionar Múltiplos Alunos

**Request:**

```http
POST /classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4/add_student
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_ids": [
    "5a2fd1c6-44ad-4033-8eb2-3eca8b924838",
    "e56ef919-cd6d-43f6-a737-181c6ef598d6",
    "abc12345-1234-1234-1234-123456789abc"
  ]
}
```

**Response:** `200 OK`

```json
{
	"message": "Students processed for class a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4",
	"added_students": [
		"5a2fd1c6-44ad-4033-8eb2-3eca8b924838",
		"e56ef919-cd6d-43f6-a737-181c6ef598d6",
		"abc12345-1234-1234-1234-123456789abc"
	],
	"total_added": 3,
	"errors": null
}
```

---

## 4. Remover Aluno da Turma

### ➖ Desvincular Aluno de uma Turma

**Endpoint:** `PUT /classes/{class_id}/remove_student`

**Descrição:** Remove um aluno de uma turma. Se o aluno não estiver em nenhuma outra turma da escola, remove também o vínculo com a escola.

### Exemplo: Remover Aluno

**Request:**

```http
PUT /classes/bcdba5f2-a193-4562-a44c-3cb077266b03/remove_student
Authorization: Bearer {token}
Content-Type: application/json

{
  "student_id": "e56ef919-cd6d-43f6-a737-181c6ef598d6"
}
```

**Response:** `200 OK`

```json
{
	"message": "Student successfully removed from class bcdba5f2-a193-4562-a44c-3cb077266b03"
}
```

**Nota:** Se o aluno não estava na turma, ainda retorna 200:

```json
{
	"message": "Student e56ef919-cd6d-43f6-a737-181c6ef598d6 is not in class bcdba5f2-a193-4562-a44c-3cb077266b03"
}
```

---

## 📋 Resumo das Rotas

| Operação            | Método | Endpoint                             | Corpo                   |
| ------------------- | ------ | ------------------------------------ | ----------------------- |
| **Mover turma**     | `PUT`  | `/classes/{class_id}`                | `{"school_id": "..."}`  |
| **Renomear turma**  | `PUT`  | `/classes/{class_id}`                | `{"name": "..."}`       |
| **Mover aluno**     | `PUT`  | `/students/{student_id}/{class_id}`  | `{"class_id": "..."}`   |
| **Adicionar aluno** | `POST` | `/classes/{class_id}/add_student`    | `{"student_id": "..."}` |
| **Remover aluno**   | `PUT`  | `/classes/{class_id}/remove_student` | `{"student_id": "..."}` |

---

## ⚠️ Comportamentos Importantes

### Realocação de Turma

- ✅ **Valida município:** Turma só pode ser movida para escola do mesmo município
- ✅ **Renomeia automaticamente:** Se nome já existe na escola destino, adiciona "(2)", "(3)", etc.
- ✅ **Atualiza alunos:** Todos os alunos da turma têm school_id e city_id atualizados

### Mudança de Aluno

- ✅ **Atualiza escola:** Se nova turma é de escola diferente, aluno é automaticamente transferido
- ✅ **Atualiza cidade:** city_id do usuário é atualizado conforme nova escola

### Remoção de Aluno

- ✅ **Desvincula turma:** aluno.class_id vira null
- ✅ **Mantém escola:** Se aluno estiver em outras turmas da mesma escola
- ✅ **Remove escola:** Se aluno não estiver em nenhuma turma da escola

---

## 🔧 Testando as Rotas

### Com cURL:

```bash
# Mover turma para outra escola
curl -X PUT "http://localhost:5000/classes/a5f6fa3a-b4fb-49e6-bee4-7f71e90b5fa4" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"school_id":"396c651f-82ee-4b7d-b3ec-35442d1b1b57"}'

# Mover aluno para outra turma
curl -X PUT "http://localhost:5000/students/e56ef919-cd6d-43f6-a737-181c6ef598d6/bcdba5f2-a193-4562-a44c-3cb077266b03" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"class_id":"957e3216-9220-4e55-8904-d21689825e95"}'
```

### Com Postman:

1. Crie requisição PUT para `/classes/{class_id}`
2. Adicione header `Authorization: Bearer {token}`
3. Adicione header `Content-Type: application/json`
4. No body (raw JSON), envie: `{"school_id": "nova-escola-id"}`
5. Envie a requisição

---

**Última atualização:** 18/02/2026
