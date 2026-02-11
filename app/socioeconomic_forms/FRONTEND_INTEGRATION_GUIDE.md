# Guia de Integração Frontend - Formulários Socioeconômicos

## 📋 Índice

1. [Criação de Formulários](#1-criação-de-formulários)
2. [Listagem de Formulários](#2-listagem-de-formulários)
3. [Obter Templates de Perguntas](#3-obter-templates-de-perguntas)
4. [Aplicação de Formulários (Responder)](#4-aplicação-de-formulários-responder)
5. [Visualização de Resultados](#5-visualização-de-resultados)

---

## 1. Criação de Formulários

### Endpoint

```http
POST /forms
Authorization: Bearer <token>
Content-Type: application/json
```

### Request Body

```typescript
interface CreateFormRequest {
	selectedSchools: string[]; // IDs das escolas
	selectedGrades: string[]; // IDs das séries (obrigatório para alunos)
	selectedClasses?: string[]; // IDs das turmas (opcional)
	deadline?: string; // ISO 8601 format
	isActive?: boolean; // Default: true
	description?: string; // Descrição opcional
	instructions?: string; // Instruções para alunos
}
```

### Exemplo de Request

```json
{
	"selectedSchools": ["escola-uuid-1"],
	"selectedGrades": [
		"pre-i-uuid", // Educação Infantil
		"1-ano-uuid", // Anos Iniciais
		"7-ano-uuid", // Anos Finais
		"eja-5-uuid" // EJA
	],
	"deadline": "2025-12-31T23:59:59Z",
	"isActive": true,
	"description": "Questionário socioeconômico para avaliação 2025"
}
```

### Response (Múltiplos Formulários)

```json
{
	"message": "2 formulário(s) criado(s) com sucesso",
	"forms": [
		{
			"id": "form-uuid-1",
			"title": "1° Questionário Socioeconômico - Educação Infantil - Escola ABC",
			"formType": "aluno-jovem",
			"description": "Questionário socioeconômico para avaliação 2025",
			"selectedSchools": ["escola-uuid-1"],
			"selectedGrades": ["pre-i-uuid", "1-ano-uuid"],
			"isActive": true,
			"deadline": "2025-12-31T23:59:59Z",
			"totalQuestions": 24,
			"recipientsCount": 150,
			"sentAt": "2025-02-09T12:00:00Z",
			"createdAt": "2025-02-09T12:00:00Z",
			"createdBy": "user-uuid"
		},
		{
			"id": "form-uuid-2",
			"title": "1° Questionário Socioeconômico - Anos Finais - Escola ABC",
			"formType": "aluno-velho",
			"description": "Questionário socioeconômico para avaliação 2025",
			"selectedSchools": ["escola-uuid-1"],
			"selectedGrades": ["7-ano-uuid", "eja-5-uuid"],
			"isActive": true,
			"deadline": "2025-12-31T23:59:59Z",
			"totalQuestions": 25,
			"recipientsCount": 200,
			"sentAt": "2025-02-09T12:00:00Z",
			"createdAt": "2025-02-09T12:00:00Z",
			"createdBy": "user-uuid"
		}
	]
}
```

### Response (Formulário Único)

```json
{
  "id": "form-uuid-1",
  "title": "1° Questionário Socioeconômico - Educação Infantil - Escola ABC",
  "formType": "aluno-jovem",
  "selectedSchools": ["escola-uuid-1"],
  "selectedGrades": ["pre-i-uuid"],
  "questions": [
    {
      "id": "q1",
      "text": "Qual é o seu curso/série atual?",
      "type": "selecao_unica",
      "options": ["Creche", "Pré I (Jardim 1)", ...],
      "required": true,
      "order": 1
    },
    // ... mais 23 perguntas
  ],
  "totalQuestions": 24,
  "recipientsCount": 150,
  "isActive": true,
  "deadline": "2025-12-31T23:59:59Z"
}
```

### Exemplo de Implementação (TypeScript)

```typescript
async function createForm(data: CreateFormRequest) {
	const response = await fetch("/forms", {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify(data),
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(error.error);
	}

	const result = await response.json();

	// Verificar se foram criados múltiplos formulários
	if (result.forms) {
		console.log(`${result.forms.length} formulários criados`);
		return result.forms;
	} else {
		console.log("Formulário único criado");
		return [result];
	}
}
```

---

## 2. Listagem de Formulários

### Endpoint

```http
GET /forms?formType={type}&isActive={boolean}&page={number}&limit={number}
Authorization: Bearer <token>
```

### Query Parameters

| Parâmetro         | Tipo    | Obrigatório | Descrição                                                                            |
| ----------------- | ------- | ----------- | ------------------------------------------------------------------------------------ |
| `formType`        | string  | Não         | Filtrar por tipo: `aluno-jovem`, `aluno-velho`, `professor`, `diretor`, `secretario` |
| `isActive`        | boolean | Não         | Filtrar por status ativo                                                             |
| `selectedSchools` | string  | Não         | IDs de escolas separados por vírgula (ex: `id1,id2,id3`)                             |
| `selectedGrades`  | string  | Não         | IDs de séries separados por vírgula (ex: `id1,id2,id3`)                              |
| `selectedClasses` | string  | Não         | IDs de turmas separados por vírgula (ex: `id1,id2,id3`)                              |
| `page`            | number  | Não         | Página (default: 1)                                                                  |
| `limit`           | number  | Não         | Itens por página (default: 20)                                                       |

### Exemplos de Request

```http
# Listar todos os formulários
GET /forms

# Listar apenas aluno-jovem
GET /forms?formType=aluno-jovem

# Listar apenas ativos
GET /forms?isActive=true

# Listar formulários aplicados na Escola ABC
GET /forms?selectedSchools=escola-abc-uuid

# Listar formulários aplicados nas Escolas ABC e XYZ
GET /forms?selectedSchools=escola-abc-uuid,escola-xyz-uuid

# Listar formulários aplicados no 5º Ano
GET /forms?selectedGrades=5-ano-uuid

# Listar formulários aplicados na Turma A do 5º Ano
GET /forms?selectedClasses=turma-a-uuid

# Paginação
GET /forms?page=2&limit=10

# Combinado: Formulários ativos do 5º Ano na Escola ABC
GET /forms?selectedSchools=escola-abc-uuid&selectedGrades=5-ano-uuid&isActive=true
```

### ⚠️ Importante sobre Filtros de Escopo

Os filtros de escopo (`selectedSchools`, `selectedGrades`, `selectedClasses`) filtram formulários que foram **aplicados** naquele escopo:

- **`selectedSchools`**: Retorna formulários onde a escola selecionada está em `selected_schools` do formulário
- **`selectedGrades`**: Retorna formulários onde a série selecionada está em `selected_grades` do formulário
- **`selectedClasses`**: Retorna formulários onde a turma selecionada está em `selected_classes` do formulário

**Exemplo Prático:**

```
Escola ABC tem:
- Formulário 1: aplicado no 5º Ano e 3º Ano
- Formulário 2: aplicado no 7º Ano e 9º Ano

GET /forms?selectedSchools=escola-abc-uuid
→ Retorna: Formulário 1 + Formulário 2

GET /forms?selectedSchools=escola-abc-uuid&selectedGrades=5-ano-uuid
→ Retorna: Apenas Formulário 1 (porque contém o 5º Ano)

GET /forms?selectedGrades=5-ano-uuid
→ Retorna: Formulário 1 + qualquer outro formulário com 5º Ano de outras escolas
```

### Response

```json
{
	"data": [
		{
			"id": "form-uuid-1",
			"title": "3° Questionário Socioeconômico - Educação Infantil - Escola ABC",
			"formType": "aluno-jovem",
			"description": "Questionário para avaliação 2025",
			"isActive": true,
			"deadline": "2025-12-31T23:59:59Z",
			"totalQuestions": 24,
			"recipientsCount": 150,
			"sentAt": "2025-02-09T12:00:00Z",
			"statistics": {
				"totalRecipients": 150,
				"totalResponses": 75,
				"completedResponses": 60,
				"partialResponses": 15,
				"pendingResponses": 75,
				"completionRate": 40.0
			},
			"createdAt": "2025-02-09T12:00:00Z",
			"updatedAt": "2025-02-09T12:00:00Z"
		}
		// ... mais formulários
	],
	"pagination": {
		"page": 1,
		"limit": 20,
		"total": 45,
		"totalPages": 3
	}
}
```

### Exemplo de Implementação (TypeScript)

```typescript
interface Form {
	id: string;
	title: string;
	formType: string;
	description?: string;
	isActive: boolean;
	deadline?: string;
	totalQuestions: number;
	recipientsCount: number;
	statistics: {
		totalRecipients: number;
		completedResponses: number;
		completionRate: number;
	};
}

interface ListFormsResponse {
	data: Form[];
	pagination: {
		page: number;
		limit: number;
		total: number;
		totalPages: number;
	};
}

async function listForms(filters?: {
	formType?: string;
	isActive?: boolean;
	selectedSchools?: string[];
	selectedGrades?: string[];
	selectedClasses?: string[];
	page?: number;
	limit?: number;
}): Promise<ListFormsResponse> {
	const params = new URLSearchParams();

	if (filters?.formType) params.append("formType", filters.formType);
	if (filters?.isActive !== undefined)
		params.append("isActive", String(filters.isActive));

	// Filtros de escopo (converter array para string separada por vírgula)
	if (filters?.selectedSchools && filters.selectedSchools.length > 0) {
		params.append("selectedSchools", filters.selectedSchools.join(","));
	}
	if (filters?.selectedGrades && filters.selectedGrades.length > 0) {
		params.append("selectedGrades", filters.selectedGrades.join(","));
	}
	if (filters?.selectedClasses && filters.selectedClasses.length > 0) {
		params.append("selectedClasses", filters.selectedClasses.join(","));
	}

	if (filters?.page) params.append("page", String(filters.page));
	if (filters?.limit) params.append("limit", String(filters.limit));

	const response = await fetch(`/forms?${params}`, {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	return response.json();
}

// Uso - Listar por tipo
const formsJovem = await listForms({
	formType: "aluno-jovem",
	isActive: true,
	page: 1,
	limit: 20,
});

// Uso - Listar formulários da Escola ABC
const formsEscolaABC = await listForms({
	selectedSchools: ["escola-abc-uuid"],
	isActive: true,
});

// Uso - Listar formulários do 5º Ano na Escola ABC
const forms5Ano = await listForms({
	selectedSchools: ["escola-abc-uuid"],
	selectedGrades: ["5-ano-uuid"],
	isActive: true,
});
```

### Exemplo de UI (React)

```tsx
function FormsList() {
	const [forms, setForms] = useState<Form[]>([]);
	const [pagination, setPagination] = useState({ page: 1, total: 0 });
	const [filters, setFilters] = useState({
		formType: "",
		isActive: true,
	});

	useEffect(() => {
		async function loadForms() {
			const response = await listForms({
				...filters,
				page: pagination.page,
				limit: 20,
			});
			setForms(response.data);
			setPagination(response.pagination);
		}
		loadForms();
	}, [filters, pagination.page]);

	return (
		<div>
			<div className="filters">
				<select
					value={filters.formType}
					onChange={(e) =>
						setFilters({ ...filters, formType: e.target.value })
					}>
					<option value="">Todos</option>
					<option value="aluno-jovem">Aluno Jovem</option>
					<option value="aluno-velho">Aluno Velho</option>
					<option value="professor">Professor</option>
				</select>

				<label>
					<input
						type="checkbox"
						checked={filters.isActive}
						onChange={(e) =>
							setFilters({
								...filters,
								isActive: e.target.checked,
							})
						}
					/>
					Apenas ativos
				</label>
			</div>

			<table>
				<thead>
					<tr>
						<th>Título</th>
						<th>Tipo</th>
						<th>Respostas</th>
						<th>Taxa Conclusão</th>
						<th>Prazo</th>
						<th>Status</th>
					</tr>
				</thead>
				<tbody>
					{forms.map((form) => (
						<tr key={form.id}>
							<td>{form.title}</td>
							<td>{form.formType}</td>
							<td>
								{form.statistics.completedResponses} /{" "}
								{form.statistics.totalRecipients}
							</td>
							<td>{form.statistics.completionRate}%</td>
							<td>
								{form.deadline
									? new Date(
											form.deadline,
										).toLocaleDateString()
									: "-"}
							</td>
							<td>{form.isActive ? "✅ Ativo" : "❌ Inativo"}</td>
						</tr>
					))}
				</tbody>
			</table>

			<Pagination
				current={pagination.page}
				total={pagination.totalPages}
				onChange={(page) => setPagination({ ...pagination, page })}
			/>
		</div>
	);
}
```

### Exemplo de UI com Filtros de Escopo (React)

```tsx
function FormsListWithScopeFilters() {
	const [forms, setForms] = useState<Form[]>([]);
	const [pagination, setPagination] = useState({ page: 1, total: 0 });
	const [filters, setFilters] = useState({
		formType: "",
		isActive: true,
		selectedSchools: [] as string[],
		selectedGrades: [] as string[],
	});

	// Carregar escolas e séries para os filtros
	const [schools, setSchools] = useState<{ id: string; name: string }[]>([]);
	const [grades, setGrades] = useState<{ id: string; name: string }[]>([]);

	useEffect(() => {
		// Carregar escolas e séries disponíveis
		async function loadOptions() {
			const schoolsData = await fetch("/schools").then((r) => r.json());
			const gradesData = await fetch("/grades").then((r) => r.json());
			setSchools(schoolsData);
			setGrades(gradesData);
		}
		loadOptions();
	}, []);

	useEffect(() => {
		async function loadForms() {
			const response = await listForms({
				...filters,
				page: pagination.page,
				limit: 20,
			});
			setForms(response.data);
			setPagination(response.pagination);
		}
		loadForms();
	}, [filters, pagination.page]);

	return (
		<div>
			<div className="filters">
				{/* Filtro por Escola */}
				<div>
					<label>Escola:</label>
					<select
						multiple
						value={filters.selectedSchools}
						onChange={(e) => {
							const selected = Array.from(
								e.target.selectedOptions,
								(option) => option.value,
							);
							setFilters({
								...filters,
								selectedSchools: selected,
							});
						}}>
						<option value="">Todas</option>
						{schools.map((school) => (
							<option key={school.id} value={school.id}>
								{school.name}
							</option>
						))}
					</select>
				</div>

				{/* Filtro por Série */}
				<div>
					<label>Série:</label>
					<select
						multiple
						value={filters.selectedGrades}
						onChange={(e) => {
							const selected = Array.from(
								e.target.selectedOptions,
								(option) => option.value,
							);
							setFilters({
								...filters,
								selectedGrades: selected,
							});
						}}>
						<option value="">Todas</option>
						{grades.map((grade) => (
							<option key={grade.id} value={grade.id}>
								{grade.name}
							</option>
						))}
					</select>
				</div>

				{/* Filtro por Tipo */}
				<select
					value={filters.formType}
					onChange={(e) =>
						setFilters({ ...filters, formType: e.target.value })
					}>
					<option value="">Todos os Tipos</option>
					<option value="aluno-jovem">Aluno Jovem</option>
					<option value="aluno-velho">Aluno Velho</option>
					<option value="professor">Professor</option>
				</select>

				{/* Filtro por Status */}
				<label>
					<input
						type="checkbox"
						checked={filters.isActive}
						onChange={(e) =>
							setFilters({
								...filters,
								isActive: e.target.checked,
							})
						}
					/>
					Apenas ativos
				</label>
			</div>

			<table>
				<thead>
					<tr>
						<th>Título</th>
						<th>Tipo</th>
						<th>Escolas</th>
						<th>Séries</th>
						<th>Respostas</th>
						<th>Taxa Conclusão</th>
						<th>Status</th>
					</tr>
				</thead>
				<tbody>
					{forms.map((form) => (
						<tr key={form.id}>
							<td>{form.title}</td>
							<td>{form.formType}</td>
							<td>
								{form.selectedSchools?.length || 0} escola(s)
							</td>
							<td>{form.selectedGrades?.length || 0} série(s)</td>
							<td>
								{form.statistics.completedResponses} /{" "}
								{form.statistics.totalRecipients}
							</td>
							<td>{form.statistics.completionRate}%</td>
							<td>{form.isActive ? "✅ Ativo" : "❌ Inativo"}</td>
						</tr>
					))}
				</tbody>
			</table>

			<Pagination
				current={pagination.page}
				total={pagination.totalPages}
				onChange={(page) => setPagination({ ...pagination, page })}
			/>
		</div>
	);
}
```

---

## 3. Obter Templates de Perguntas

Antes de exibir o formulário para o aluno responder, você precisa buscar as perguntas do formulário específico.

### Endpoint - Obter Formulário Completo

```http
GET /forms/{formId}?includeQuestions=true
Authorization: Bearer <token>
```

### Response

```json
{
	"id": "form-uuid-1",
	"title": "1° Questionário Socioeconômico - Educação Infantil - Escola ABC",
	"formType": "aluno-jovem",
	"description": "Questionário para avaliação 2025",
	"instructions": "Por favor, responda todas as perguntas com sinceridade.",
	"questions": [
		{
			"id": "q1",
			"text": "Qual é o seu curso/série atual?",
			"type": "selecao_unica",
			"options": [
				"Creche",
				"Pré I (Jardim 1)",
				"Pré II (Jardim 2)",
				"1º Ano",
				"2º Ano",
				"3º Ano",
				"4º Ano",
				"5º Ano"
			],
			"required": true,
			"order": 1
		},
		{
			"id": "q2",
			"text": "Qual é a sua idade?",
			"type": "selecao_unica",
			"options": [
				"Menos de 3 anos",
				"3 anos",
				"4 anos",
				"5 anos",
				"6 anos",
				"7 anos",
				"8 anos",
				"9 anos",
				"10 anos",
				"11 anos",
				"12 anos",
				"13 anos ou mais"
			],
			"required": true,
			"order": 2
		},
		{
			"id": "q6",
			"text": "Você possui deficiência, transtorno do espectro autista ou superdotação?",
			"type": "matriz_selecao",
			"subQuestions": [
				{
					"id": "q6a",
					"text": "Deficiência"
				},
				{
					"id": "q6b",
					"text": "Transtorno do espectro autista"
				},
				{
					"id": "q6c",
					"text": "Altas habilidades ou superdotação"
				}
			],
			"options": ["Não", "Sim"],
			"required": true,
			"order": 6
		}
		// ... mais 21 perguntas (total 24)
	],
	"totalQuestions": 24,
	"isActive": true,
	"deadline": "2025-12-31T23:59:59Z"
}
```

### Exemplo de Implementação

```typescript
interface Question {
	id: string;
	text: string;
	type: "selecao_unica" | "matriz_selecao" | "multipla_escolha" | "slider";
	options?: string[];
	subQuestions?: { id: string; text: string }[];
	required: boolean;
	order: number;
	min?: number;
	max?: number;
}

interface FormWithQuestions {
	id: string;
	title: string;
	formType: string;
	description?: string;
	instructions?: string;
	questions: Question[];
	totalQuestions: number;
	deadline?: string;
}

async function getFormWithQuestions(
	formId: string,
): Promise<FormWithQuestions> {
	const response = await fetch(`/forms/${formId}?includeQuestions=true`, {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});

	if (!response.ok) {
		throw new Error("Erro ao carregar formulário");
	}

	return response.json();
}
```

---

## 4. Aplicação de Formulários (Responder)

### 4.1. Verificar se Aluno Tem Formulário Pendente

```http
GET /forms/responses/my-forms
Authorization: Bearer <token> (do aluno)
```

### Response

```json
{
	"pendingForms": [
		{
			"formId": "form-uuid-1",
			"title": "1° Questionário Socioeconômico - Educação Infantil - Escola ABC",
			"formType": "aluno-jovem",
			"deadline": "2025-12-31T23:59:59Z",
			"status": "pending",
			"sentAt": "2025-02-09T12:00:00Z"
		}
	],
	"completedForms": [
		{
			"formId": "form-uuid-old",
			"title": "Questionário Anterior",
			"formType": "aluno-jovem",
			"status": "completed",
			"completedAt": "2025-01-15T14:30:00Z"
		}
	]
}
```

### 4.2. Iniciar Resposta

```http
POST /forms/{formId}/responses
Authorization: Bearer <token> (do aluno)
Content-Type: application/json
```

### Request Body

```json
{
	"answers": {
		"q1": "1º Ano",
		"q2": "6 anos",
		"q3": "Masculino",
		"q6a": "Não",
		"q6b": "Não",
		"q6c": "Não"
		// ... todas as respostas
	}
}
```

### Response

```json
{
  "id": "response-uuid-1",
  "formId": "form-uuid-1",
  "userId": "student-uuid",
  "answers": { ... },
  "status": "completed",
  "submittedAt": "2025-02-09T14:30:00Z",
  "message": "Resposta enviada com sucesso!"
}
```

### Estrutura de Respostas por Tipo de Pergunta

#### Seleção Única (selecao_unica)

```json
{
	"q1": "1º Ano", // string - uma opção
	"q2": "6 anos"
}
```

#### Matriz de Seleção (matriz_selecao)

```json
{
	"q6a": "Não", // Cada subpergunta tem sua resposta
	"q6b": "Não",
	"q6c": "Sim"
}
```

#### Múltipla Escolha (multipla_escolha)

```json
{
	"q13": ["Opção 1", "Opção 3", "Opção 5"] // array - múltiplas opções
}
```

#### Slider (slider)

```json
{
	"q15": 7 // number - valor numérico
}
```

### Exemplo de Implementação Completa

```typescript
interface Answer {
	[questionId: string]: string | string[] | number;
}

interface SubmitResponseRequest {
	answers: Answer;
}

async function submitFormResponse(
	formId: string,
	answers: Answer,
): Promise<void> {
	const response = await fetch(`/forms/${formId}/responses`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${studentToken}`,
		},
		body: JSON.stringify({ answers }),
	});

	if (!response.ok) {
		const error = await response.json();
		throw new Error(error.error || "Erro ao enviar resposta");
	}

	return response.json();
}
```

### Exemplo de Componente de Formulário (React)

```tsx
function FormApplication({ formId }: { formId: string }) {
	const [form, setForm] = useState<FormWithQuestions | null>(null);
	const [answers, setAnswers] = useState<Answer>({});
	const [loading, setLoading] = useState(true);
	const [submitting, setSubmitting] = useState(false);

	useEffect(() => {
		async function loadForm() {
			try {
				const data = await getFormWithQuestions(formId);
				setForm(data);
			} catch (error) {
				console.error("Erro ao carregar formulário:", error);
			} finally {
				setLoading(false);
			}
		}
		loadForm();
	}, [formId]);

	const handleAnswerChange = (questionId: string, value: any) => {
		setAnswers((prev) => ({
			...prev,
			[questionId]: value,
		}));
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();

		// Validar campos obrigatórios
		const requiredQuestions = form!.questions.filter((q) => q.required);
		const missingAnswers = requiredQuestions.filter((q) => {
			if (q.type === "matriz_selecao") {
				return q.subQuestions!.some((sq) => !answers[sq.id]);
			}
			return !answers[q.id];
		});

		if (missingAnswers.length > 0) {
			alert("Por favor, responda todas as perguntas obrigatórias");
			return;
		}

		setSubmitting(true);
		try {
			await submitFormResponse(formId, answers);
			alert("Formulário enviado com sucesso!");
			// Redirecionar ou mostrar mensagem de sucesso
		} catch (error) {
			alert("Erro ao enviar formulário: " + error.message);
		} finally {
			setSubmitting(false);
		}
	};

	if (loading) return <div>Carregando formulário...</div>;
	if (!form) return <div>Formulário não encontrado</div>;

	return (
		<form onSubmit={handleSubmit}>
			<h1>{form.title}</h1>

			{form.instructions && (
				<div className="instructions">
					<p>{form.instructions}</p>
				</div>
			)}

			{form.deadline && (
				<div className="deadline">
					Prazo: {new Date(form.deadline).toLocaleDateString()}
				</div>
			)}

			{form.questions
				.sort((a, b) => a.order - b.order)
				.map((question) => (
					<QuestionRenderer
						key={question.id}
						question={question}
						value={answers[question.id]}
						onChange={(value) =>
							handleAnswerChange(question.id, value)
						}
					/>
				))}

			<button type="submit" disabled={submitting}>
				{submitting ? "Enviando..." : "Enviar Respostas"}
			</button>
		</form>
	);
}
```

### Componente de Renderização de Perguntas

```tsx
function QuestionRenderer({
	question,
	value,
	onChange,
}: {
	question: Question;
	value: any;
	onChange: (value: any) => void;
}) {
	switch (question.type) {
		case "selecao_unica":
			return (
				<div className="question">
					<label>
						{question.text}
						{question.required && (
							<span className="required">*</span>
						)}
					</label>

					{question.options?.map((option) => (
						<label key={option}>
							<input
								type="radio"
								name={question.id}
								value={option}
								checked={value === option}
								onChange={(e) => onChange(e.target.value)}
								required={question.required}
							/>
							{option}
						</label>
					))}
				</div>
			);

		case "matriz_selecao":
			return (
				<div className="question-matrix">
					<label>
						{question.text}
						{question.required && (
							<span className="required">*</span>
						)}
					</label>

					<table>
						<thead>
							<tr>
								<th></th>
								{question.options?.map((option) => (
									<th key={option}>{option}</th>
								))}
							</tr>
						</thead>
						<tbody>
							{question.subQuestions?.map((subQ) => (
								<tr key={subQ.id}>
									<td>{subQ.text}</td>
									{question.options?.map((option) => (
										<td key={option}>
											<input
												type="radio"
												name={subQ.id}
												value={option}
												checked={
													value?.[subQ.id] === option
												}
												onChange={(e) => {
													onChange({
														...value,
														[subQ.id]:
															e.target.value,
													});
												}}
												required={question.required}
											/>
										</td>
									))}
								</tr>
							))}
						</tbody>
					</table>
				</div>
			);

		case "multipla_escolha":
			return (
				<div className="question">
					<label>
						{question.text}
						{question.required && (
							<span className="required">*</span>
						)}
					</label>

					{question.options?.map((option) => (
						<label key={option}>
							<input
								type="checkbox"
								value={option}
								checked={
									Array.isArray(value) &&
									value.includes(option)
								}
								onChange={(e) => {
									const newValue = Array.isArray(value)
										? [...value]
										: [];
									if (e.target.checked) {
										newValue.push(option);
									} else {
										const index = newValue.indexOf(option);
										if (index > -1)
											newValue.splice(index, 1);
									}
									onChange(newValue);
								}}
							/>
							{option}
						</label>
					))}
				</div>
			);

		case "slider":
			return (
				<div className="question">
					<label>
						{question.text}
						{question.required && (
							<span className="required">*</span>
						)}
					</label>

					<input
						type="range"
						min={question.min || 0}
						max={question.max || 100}
						value={value || question.min || 0}
						onChange={(e) => onChange(parseInt(e.target.value))}
						required={question.required}
					/>
					<span>{value || question.min || 0}</span>
				</div>
			);

		default:
			return null;
	}
}
```

---

## 5. Visualização de Resultados

### 5.1. Obter Resultados de um Formulário

```http
GET /forms/{formId}/results
Authorization: Bearer <token>
```

### Response

```json
{
	"formId": "form-uuid-1",
	"title": "1° Questionário Socioeconômico - Educação Infantil - Escola ABC",
	"statistics": {
		"totalRecipients": 150,
		"totalResponses": 120,
		"completedResponses": 100,
		"partialResponses": 20,
		"pendingResponses": 30,
		"completionRate": 66.67
	},
	"results": [
		{
			"questionId": "q1",
			"questionText": "Qual é o seu curso/série atual?",
			"type": "selecao_unica",
			"responses": {
				"Creche": 10,
				"Pré I (Jardim 1)": 25,
				"Pré II (Jardim 2)": 30,
				"1º Ano": 35
			},
			"totalResponses": 100
		},
		{
			"questionId": "q2",
			"questionText": "Qual é a sua idade?",
			"type": "selecao_unica",
			"responses": {
				"3 anos": 5,
				"4 anos": 15,
				"5 anos": 20,
				"6 anos": 35,
				"7 anos": 20,
				"8 anos": 5
			},
			"totalResponses": 100
		}
	]
}
```

### 5.2. Obter Resultados Agregados

```http
GET /forms/results/aggregated?schoolId={id}&formType={type}
Authorization: Bearer <token>
```

### Response

```json
{
	"school": {
		"id": "escola-uuid-1",
		"name": "Escola ABC"
	},
	"formType": "aluno-jovem",
	"totalForms": 3,
	"totalResponses": 450,
	"aggregatedResults": {
		"demographics": {
			"gender": {
				"Masculino": 230,
				"Feminino": 220
			},
			"age": {
				"6 anos": 120,
				"7 anos": 150,
				"8 anos": 180
			}
		},
		"socioeconomic": {
			"hasInternet": {
				"Sim": 400,
				"Não": 50
			},
			"parentsEducation": {
				"Ensino Fundamental": 200,
				"Ensino Médio": 150,
				"Ensino Superior": 100
			}
		}
	}
}
```

---

## 📚 Resumo de Endpoints

| Método | Endpoint                                                            | Descrição                                  |
| ------ | ------------------------------------------------------------------- | ------------------------------------------ |
| POST   | `/forms`                                                            | Criar formulário(s)                        |
| GET    | `/forms?selectedSchools=...&selectedGrades=...&selectedClasses=...` | Listar formulários (com filtros de escopo) |
| GET    | `/forms/{id}`                                                       | Obter formulário específico                |
| GET    | `/forms/templates`                                                  | Listar templates disponíveis               |
| GET    | `/forms/templates/{type}`                                           | Obter template específico                  |
| GET    | `/forms/responses/my-forms`                                         | Formulários do aluno (pendentes/completos) |
| POST   | `/forms/{id}/responses`                                             | Enviar respostas                           |
| GET    | `/forms/{id}/results`                                               | Obter resultados                           |
| GET    | `/forms/results/aggregated`                                         | Resultados agregados                       |

### Filtros de Escopo (GET /forms)

Os seguintes query parameters estão disponíveis para filtrar formulários por escopo de aplicação:

- `selectedSchools`: Filtrar por escolas onde o formulário foi aplicado (separados por vírgula)
- `selectedGrades`: Filtrar por séries onde o formulário foi aplicado (separados por vírgula)
- `selectedClasses`: Filtrar por turmas onde o formulário foi aplicado (separados por vírgula)
- `formType`: Filtrar por tipo de formulário
- `isActive`: Filtrar por status ativo (true/false)
- `page`: Número da página (paginação)
- `limit`: Itens por página (paginação)

---

## ⚠️ Observações Importantes

### Permissões

- **Admin/TecAdm**: Criar, listar, visualizar resultados
- **Aluno**: Visualizar formulários atribuídos, responder
- **Professor/Diretor**: Visualizar resultados da sua escola

### Validações

- **Perguntas obrigatórias** devem ser respondidas
- **Respostas de matriz** devem incluir todas as subperguntas
- **Deadline** é verificado ao enviar (não pode responder após prazo)

### Estados do Formulário

- `pending`: Enviado ao aluno, não iniciado
- `in_progress`: Iniciado mas não finalizado
- `completed`: Finalizado e enviado

### Tipos de Perguntas

- `selecao_unica`: Radio button (uma opção)
- `matriz_selecao`: Tabela com múltiplas linhas
- `multipla_escolha`: Checkbox (múltiplas opções)
- `slider`: Escala numérica

---

## 🔧 Dicas de Implementação

### 1. Salvamento Automático (Rascunho)

Considere implementar salvamento automático das respostas:

```typescript
// Salvar localmente a cada mudança
useEffect(() => {
	localStorage.setItem(`form-${formId}-draft`, JSON.stringify(answers));
}, [answers, formId]);

// Recuperar ao carregar
useEffect(() => {
	const draft = localStorage.getItem(`form-${formId}-draft`);
	if (draft) {
		setAnswers(JSON.parse(draft));
	}
}, [formId]);
```

### 2. Validação em Tempo Real

```typescript
function validateAnswer(question: Question, answer: any): string | null {
	if (question.required && !answer) {
		return "Esta pergunta é obrigatória";
	}

	if (question.type === "matriz_selecao") {
		const missingSubQuestions = question.subQuestions!.filter(
			(sq) => !answer?.[sq.id],
		);
		if (missingSubQuestions.length > 0) {
			return "Responda todas as linhas da tabela";
		}
	}

	return null;
}
```

### 3. Indicador de Progresso

```typescript
function calculateProgress(questions: Question[], answers: Answer): number {
	let totalRequired = 0;
	let answered = 0;

	questions.forEach((q) => {
		if (!q.required) return;

		if (q.type === "matriz_selecao") {
			totalRequired += q.subQuestions!.length;
			answered += q.subQuestions!.filter((sq) => answers[sq.id]).length;
		} else {
			totalRequired++;
			if (answers[q.id]) answered++;
		}
	});

	return (answered / totalRequired) * 100;
}
```

---

Documentação completa! 🎉
