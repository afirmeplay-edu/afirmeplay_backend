# Criação Automática de Formulários Socioeconômicos

## 🎯 Funcionalidade

Sistema de criação automática de formulários que detecta quando séries de diferentes education stages são selecionadas e cria múltiplos formulários automaticamente.

## ✨ Recursos Implementados

### 1. **Criação Automática Múltipla**

Quando séries de diferentes education stages são selecionadas (ex: Educação Infantil + Anos Finais), o sistema:

- Detecta automaticamente os diferentes types
- Cria um formulário para cada tipo
- Distribui os recipients apropriados para cada um

### 2. **Títulos Automáticos**

Títulos são gerados automaticamente no formato:

```
"{N}° Questionário Socioeconômico - {Education Stage} - {Escola}"
```

**Exemplos:**

- `"1° Questionário Socioeconômico - Educação Infantil - Escola XYZ"`
- `"2° Questionário Socioeconômico - Anos Finais - Escola ABC"`
- `"3° Questionário Socioeconômico - EJA - Escola DEF"`

### 3. **Contagem de Aplicações**

O sistema conta automaticamente quantas vezes cada tipo de formulário foi aplicado na escola:

- Contagem por `form_type` (aluno-jovem, aluno-velho)
- Contagem por `school_id`
- Independente das séries específicas

**Exemplo:**

- Escola XYZ já teve 2 aplicações de formulário "aluno-jovem"
- Nova aplicação será a "3ª"

### 4. **Carregamento Automático de Templates**

Se perguntas não forem fornecidas, o sistema carrega automaticamente do template correspondente:

- `aluno-jovem` → 24 perguntas
- `aluno-velho` → 25 perguntas

### 5. **Validação de Séries**

Antes de criar qualquer formulário, o sistema valida que **todas** as séries existem no banco de dados:

- Se alguma série não existir → ERRO
- Nenhum formulário é criado parcialmente
- Validação atômica

## 📝 Uso da API

### Request

```http
POST /forms
Authorization: Bearer <token>
Content-Type: application/json

{
  "selectedSchools": ["escola-xyz-id"],
  "selectedGrades": [
    "pre-i-id",      // Educação Infantil
    "1-ano-id",      // Anos Iniciais
    "7-ano-id",      // Anos Finais
    "eja-5-id"       // EJA
  ],
  "deadline": "2025-12-31T23:59:59Z",
  "isActive": true
}
```

**Campos removidos:**

- ❌ `title` - Agora é gerado automaticamente
- ❌ `formType` - Detectado automaticamente pelas séries
- ❌ `questions` - Carregadas automaticamente dos templates

### Response (Múltiplos Formulários)

```json
{
	"message": "2 formulário(s) criado(s) com sucesso",
	"forms": [
		{
			"id": "form-uuid-1",
			"title": "3° Questionário Socioeconômico - Educação Infantil - Escola XYZ",
			"formType": "aluno-jovem",
			"selectedSchools": ["escola-xyz-id"],
			"selectedGrades": ["pre-i-id", "1-ano-id"],
			"totalQuestions": 24,
			"recipientsCount": 150,
			"sentAt": "2025-02-09T12:00:00Z",
			"isActive": true,
			"deadline": "2025-12-31T23:59:59Z"
		},
		{
			"id": "form-uuid-2",
			"title": "1° Questionário Socioeconômico - Anos Finais - Escola XYZ",
			"formType": "aluno-velho",
			"selectedSchools": ["escola-xyz-id"],
			"selectedGrades": ["7-ano-id", "eja-5-id"],
			"totalQuestions": 25,
			"recipientsCount": 200,
			"sentAt": "2025-02-09T12:00:00Z",
			"isActive": true,
			"deadline": "2025-12-31T23:59:59Z"
		}
	]
}
```

### Response (Formulário Único)

```json
{
  "id": "form-uuid-1",
  "title": "1° Questionário Socioeconômico - Educação Infantil - Escola XYZ",
  "formType": "aluno-jovem",
  "selectedSchools": ["escola-xyz-id"],
  "selectedGrades": ["pre-i-id", "1-ano-id"],
  "questions": [...],
  "totalQuestions": 24,
  "recipientsCount": 150,
  "isActive": true
}
```

## 🔄 Fluxo de Criação

```
1. Validar Dados
   ├─ Verificar se selectedGrades foi fornecido
   └─ Validar filtros (se houver)

2. Validar Séries
   ├─ Buscar TODAS as séries no banco (Grade.query)
   ├─ Se alguma não existir → ERRO
   └─ Retornar objetos Grade

3. Agrupar por Education Stage
   ├─ Para cada Grade, pegar education_stage_id
   ├─ Mapear para form_type (aluno-jovem ou aluno-velho)
   └─ Agrupar: { 'aluno-jovem': [...], 'aluno-velho': [...] }

4. Para cada Grupo
   ├─ Contar aplicações anteriores (school + form_type)
   ├─ Gerar título automático
   ├─ Carregar perguntas do template
   ├─ Criar Form
   └─ Criar FormQuestions

5. Distribuir Recipients
   ├─ Para cada formulário criado
   ├─ Determinar destinatários (DistributionService)
   └─ Criar FormRecipient para cada aluno

6. Retornar Resposta
   └─ Lista de formulários OU formulário único
```

## 📊 Mapeamento Education Stage → Form Type

```python
EDUCATION_STAGE_TO_FORM_TYPE = {
    # aluno-jovem
    'd1142d12-ed98-46f4-ae78-62c963371464': 'aluno-jovem',  # Educação Infantil
    '614b7d10-b758-42ec-a04e-86f78dc7740a': 'aluno-jovem',  # Anos Iniciais

    # aluno-velho
    'c78fcd8e-00a1-485d-8c03-70bcf59e3025': 'aluno-velho',  # Anos Finais
    '63cb6876-3221-4fa2-89e8-a82ad1733032': 'aluno-velho',  # EJA (removido do aluno-jovem)
}
```

## ⚠️ Observações Importantes

### Séries do Sistema vs Perguntas do Formulário

São coisas **diferentes** e **independentes**:

**A) Séries do Sistema (Grade model):**

- Usadas para **aplicar** o formulário
- Devem existir no banco de dados
- Validadas antes de criar formulário

**B) Opções da Pergunta q1:**

- Usadas para o **aluno responder**
- Podem não existir no sistema
- São independentes das séries cadastradas

**Exemplo:**

- Grade "Creche" pode não existir no banco
- Mas aluno pode responder que estuda na "Creche" na pergunta q1
- Isso é normal e esperado!

### EJA Agora em aluno-velho

- ✅ EJA agora está **incluído** no `aluno-velho`
- ❌ EJA foi **removido** do `aluno-jovem`
- ✅ Formulário `aluno-velho` tem 25 perguntas (inclui q25 sobre planos futuros)

### Contagem Compartilhada

A contagem de aplicações é compartilhada por:

- `form_type` (aluno-jovem ou aluno-velho)
- `school_id`

**Não depende de:**

- Séries específicas selecionadas
- Turmas específicas
- Education stages individuais

## 🔧 Métodos Auxiliares Criados

### `FormService._validate_grades_exist(grade_ids)`

Valida que todas as séries existem no banco de dados.

### `FormService._group_grades_by_form_type(grades)`

Agrupa séries por tipo de formulário baseado no education_stage_id.

### `FormService._count_previous_applications(form_type, school_id)`

Conta aplicações anteriores deste tipo na escola.

### `FormService._generate_title(form_type, school_id, grade_ids, application_number)`

Gera título automático no formato padronizado.

### `FormService._create_single_form(data, created_by)`

Cria um único formulário (método interno).

## 🚨 Erros Possíveis

### Série não encontrada

```json
{
	"error": "Série(s) não encontrada(s) no sistema: uuid-1, uuid-2"
}
```

### selectedGrades obrigatório

```json
{
	"error": "selectedGrades é obrigatório para formulários de alunos"
}
```

### Template não encontrado

```json
{
	"error": "Template para 'aluno-jovem' não encontrado e perguntas não fornecidas"
}
```

## 📈 Benefícios

1. ✅ **Automação**: Admin não precisa criar múltiplos formulários manualmente
2. ✅ **Consistência**: Títulos sempre no mesmo formato
3. ✅ **Rastreabilidade**: Contagem automática de aplicações
4. ✅ **Segurança**: Validação atômica de séries
5. ✅ **Flexibilidade**: Suporta escolas com múltiplos segmentos
6. ✅ **Manutenibilidade**: Templates centralizados

## 🔄 Migração do Frontend

### Antes (Hardcoded)

```typescript
const payload = {
  title: "Questionário 2025",
  formType: "aluno-jovem",
  questions: [...24 perguntas hardcoded...],
  selectedSchools: [...],
  selectedGrades: [...]
};
```

### Depois (Automático)

```typescript
const payload = {
  // title removido - gerado automaticamente
  // formType removido - detectado automaticamente
  // questions removido - carregado do template
  selectedSchools: [...],
  selectedGrades: [...],
  deadline: "2025-12-31T23:59:59Z"
};

// Sistema detecta automaticamente e cria formulários necessários
```

## 📚 Documentação Relacionada

- `templates/README.md` - Documentação dos templates de perguntas
- `templates/USAGE.md` - Guia de uso dos templates
- `templates/aluno_jovem_questions.json` - Template aluno-jovem (24 perguntas)
- `templates/aluno_velho_questions.json` - Template aluno-velho (25 perguntas)
