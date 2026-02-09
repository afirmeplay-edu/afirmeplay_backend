# Guia de Uso dos Templates de Formulários

## Visão Geral

Os templates de formulários socioeconômicos fornecem perguntas padrão pré-definidas para diferentes tipos de questionários. Atualmente, os templates disponíveis são:

- **aluno-jovem**: Questionário para Educação Infantil e Anos Iniciais (Creche, Pré I, Pré II, 1º ao 5º ano)
- **aluno-velho**: Questionário para Anos Finais (4º ao 9º ano) e EJA (1º ao 9º Período)

## Via API

### 1. Listar Templates Disponíveis

```http
GET /forms/templates
Authorization: Bearer <token>
```

**Resposta:**

```json
{
	"templates": ["aluno-jovem", "aluno-velho"],
	"total": 2
}
```

### 2. Obter Template Completo

```http
GET /forms/templates/aluno-jovem
Authorization: Bearer <token>
```

**Resposta:**

```json
{
  "formType": "aluno-jovem",
  "title": "Questionário Socioeconômico - Aluno Jovem",
  "description": "Questionário para alunos da Educação Infantil e Anos Iniciais",
  "questions": [
    {
      "id": "q1",
      "text": "Qual é o seu curso/série atual?",
      "type": "selecao_unica",
      "options": ["Creche", "Pré I (Jardim 1)", ...],
      "required": true,
      "order": 1
    },
    ...
  ]
}
```

### 3. Obter Apenas as Perguntas

```http
GET /forms/templates/aluno-jovem/questions
Authorization: Bearer <token>
```

**Resposta:**

```json
{
  "formType": "aluno-jovem",
  "questions": [...],
  "totalQuestions": 24
}
```

### 4. Criar Formulário com Template

```http
POST /forms
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Questionário Socioeconômico 2025",
  "description": "Aplicação do questionário SAEB",
  "formType": "aluno-jovem",
  "targetGroups": ["alunos"],
  "selectedSchools": ["uuid-escola-1", "uuid-escola-2"],
  "selectedGrades": ["uuid-serie-1", "uuid-serie-2"],
  "isActive": true,
  "deadline": "2025-12-31T23:59:59Z",
  "questions": [
    {
      "id": "q1",
      "text": "Qual é o seu curso/série atual?",
      "type": "selecao_unica",
      "options": ["Creche", "Pré I (Jardim 1)", ...],
      "required": true,
      "order": 1
    },
    ...todas as 24 perguntas do template...
  ]
}
```

## Via Código Python

### 1. Carregar Template

```python
from app.socioeconomic_forms.services import TemplateService

# Carregar template completo
template = TemplateService.load_template('aluno-jovem')
print(template['title'])  # "Questionário Socioeconômico - Aluno Jovem"
print(len(template['questions']))  # 24

# Carregar apenas perguntas
questions = TemplateService.get_questions('aluno-jovem')
print(questions[0]['id'])  # "q1"
print(questions[0]['text'])  # "Qual é o seu curso/série atual?"
```

### 2. Criar Formulário com Template

```python
from app.socioeconomic_forms.services import TemplateService, FormService

# Opção 1: Criar payload com template
payload = TemplateService.create_form_with_template(
    'aluno-jovem',
    title='Questionário 2025',
    targetGroups=['alunos'],
    selectedSchools=['uuid-escola-1'],
    selectedGrades=['uuid-serie-1'],
    isActive=True
)

# Opção 2: Carregar template e customizar
template = TemplateService.load_template('aluno-jovem')
form = FormService.create_form(
    data={
        'title': 'Questionário Customizado',
        'description': template['description'],
        'formType': 'aluno-jovem',
        'questions': template['questions'],  # Usar perguntas do template
        'targetGroups': ['alunos'],
        'selectedSchools': ['uuid-escola-1'],
        'selectedGrades': ['uuid-serie-1']
    },
    created_by='user-id'
)
```

### 3. Customizar Perguntas do Template

```python
# Carregar template
template = TemplateService.load_template('aluno-jovem')
questions = template['questions']

# Adicionar uma nova pergunta
questions.append({
    "id": "q25",
    "text": "Pergunta adicional customizada",
    "type": "selecao_unica",
    "options": ["Opção 1", "Opção 2"],
    "required": False,
    "order": 25
})

# Modificar uma pergunta existente
for question in questions:
    if question['id'] == 'q1':
        question['required'] = False  # Tornar opcional

# Usar as perguntas customizadas
form = FormService.create_form(
    data={
        'title': 'Formulário Customizado',
        'formType': 'aluno-jovem',
        'questions': questions,  # Perguntas modificadas
        'targetGroups': ['alunos'],
        'selectedSchools': ['uuid-escola-1'],
        'selectedGrades': ['uuid-serie-1']
    },
    created_by='user-id'
)
```

## Novas Perguntas do Aluno-Jovem

### Pergunta q1: Curso/Série (NOVA)

```json
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
}
```

**Objetivo:** Identificar o curso/série do aluno para análise de distorção idade-série.

### Pergunta q2: Idade (NOVA)

```json
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
}
```

**Objetivo:** Identificar a idade do aluno para análise de distorção idade-série.

### Análise de Distorção Idade-Série

Com as perguntas q1 (curso/série) e q2 (idade), é possível calcular:

```python
# Exemplo de análise
def calcular_distorcao(curso, idade):
    """
    Calcula se o aluno está com idade certa, defasagem ou distorção

    Returns:
        "idade_certa" | "defasagem" | "distorcao"
    """
    mapeamento = {
        "Creche": {"idade_certa": [0, 1, 2, 3], "defasagem": [4], "distorcao": 5},
        "Pré I (Jardim 1)": {"idade_certa": [4], "defasagem": [5], "distorcao": 6},
        "Pré II (Jardim 2)": {"idade_certa": [5], "defasagem": [6], "distorcao": 7},
        "1º Ano": {"idade_certa": [6], "defasagem": [7], "distorcao": 8},
        "2º Ano": {"idade_certa": [7], "defasagem": [8], "distorcao": 9},
        "3º Ano": {"idade_certa": [8], "defasagem": [9], "distorcao": 10},
        "4º Ano": {"idade_certa": [9], "defasagem": [10], "distorcao": 11},
        "5º Ano": {"idade_certa": [10], "defasagem": [11], "distorcao": 12},
    }

    if curso not in mapeamento:
        return "desconhecido"

    config = mapeamento[curso]

    if idade in config["idade_certa"]:
        return "idade_certa"
    elif idade in config["defasagem"]:
        return "defasagem"
    elif idade >= config["distorcao"]:
        return "distorcao"
    else:
        return "antes_da_idade"

# Uso
resultado = calcular_distorcao("5º Ano", 12)
print(resultado)  # "distorcao"
```

## Novas Perguntas do Aluno-Velho

### Pergunta q1: Curso/Série/Ano (NOVA)

```json
{
	"id": "q1",
	"text": "Qual é o seu curso/série/ano atual?",
	"type": "selecao_unica",
	"options": [
		"4º Ano",
		"5º Ano",
		"6º Ano",
		"7º Ano",
		"8º Ano",
		"9º Ano",
		"EJA 1º Período",
		"EJA 2º Período",
		"EJA 3º Período",
		"EJA 4º Período",
		"EJA 5º Período",
		"EJA 6º Período",
		"EJA 7º Período",
		"EJA 8º Período",
		"EJA 9º Período"
	],
	"required": true,
	"order": 1
}
```

**Objetivo:** Identificar o curso/série/ano do aluno, incluindo períodos EJA, para análise de distorção idade-série.

### Pergunta q2: Idade (NOVA)

```json
{
	"id": "q2",
	"text": "Qual é a sua idade?",
	"type": "selecao_unica",
	"options": [
		"13 anos ou menos",
		"14 anos",
		"15 anos",
		"16 anos",
		"17 anos",
		"18 anos ou mais"
	],
	"required": true,
	"order": 2
}
```

**Objetivo:** Identificar a idade do aluno (faixa etária de Anos Finais e EJA) para análise de distorção idade-série.

### Pergunta q25: Planos Futuros (NOVA - exclusiva do aluno-velho)

```json
{
	"id": "q25",
	"text": "Quando terminar o Ensino Fundamental, você pretende:",
	"type": "selecao_unica",
	"options": [
		"Somente continuar estudando",
		"Somente trabalhar",
		"Continuar estudando e trabalhar",
		"Ainda não sei"
	],
	"required": true,
	"order": 25
}
```

**Objetivo:** Identificar as expectativas e planos do aluno após a conclusão do Ensino Fundamental.

### Análise de Distorção Idade-Série (Aluno-Velho)

```python
# Exemplo de análise para aluno-velho
def calcular_distorcao_velho(curso, idade):
    """
    Calcula se o aluno está com idade certa, defasagem ou distorção

    Returns:
        "idade_certa" | "defasagem" | "distorcao" | "eja_adequado" | "eja_inadequado"
    """
    # Para EJA: idade mínima é 15 anos
    if curso.startswith("EJA"):
        return "eja_adequado" if idade >= 15 else "eja_inadequado"

    mapeamento = {
        "4º Ano": {"idade_certa": [9], "defasagem": [10], "distorcao": 11},
        "5º Ano": {"idade_certa": [10], "defasagem": [11], "distorcao": 12},
        "6º Ano": {"idade_certa": [11], "defasagem": [12], "distorcao": 13},
        "7º Ano": {"idade_certa": [12], "defasagem": [13], "distorcao": 14},
        "8º Ano": {"idade_certa": [13], "defasagem": [14], "distorcao": 15},
        "9º Ano": {"idade_certa": [14], "defasagem": [15], "distorcao": 16},
    }

    if curso not in mapeamento:
        return "desconhecido"

    config = mapeamento[curso]

    if idade in config["idade_certa"]:
        return "idade_certa"
    elif idade in config["defasagem"]:
        return "defasagem"
    elif idade >= config["distorcao"]:
        return "distorcao"
    else:
        return "antes_da_idade"

# Exemplos de uso
print(calcular_distorcao_velho("9º Ano", 16))  # "distorcao"
print(calcular_distorcao_velho("EJA 5º Período", 17))  # "eja_adequado"
print(calcular_distorcao_velho("EJA 3º Período", 14))  # "eja_inadequado"
```

## Permissões

As rotas de templates requerem autenticação JWT e as seguintes roles:

- `admin`
- `tecadm`

## Observações Importantes

### aluno-jovem:

- ⚠️ **EJA NÃO está incluído**: Apenas para Educação Infantil e Anos Iniciais
- ✅ Total de 24 perguntas obrigatórias
- ✅ Perguntas baseadas no questionário SAEB 2023 do 5º ano
- ✅ Faixa etária: Menos de 3 anos até 13 anos ou mais

### aluno-velho:

- ✅ **EJA ESTÁ incluído**: Para Anos Finais (4º ao 9º ano) e EJA (1º ao 9º Período)
- ✅ Total de 25 perguntas obrigatórias (inclui q25 sobre planos futuros)
- ✅ Perguntas baseadas no questionário SAEB 2023 do 9º ano
- ✅ Faixa etária: 13 anos ou menos até 18 anos ou mais
- ✅ q1 com 15 opções (6 anos do ensino regular + 9 períodos EJA)
- ✅ EJA tem regra especial: idade mínima de 15 anos

### Geral:

- ✅ Templates podem ser customizados antes de criar o formulário
- ✅ Todas as perguntas são obrigatórias por padrão
- ✅ Suporte para análise de distorção idade-série
