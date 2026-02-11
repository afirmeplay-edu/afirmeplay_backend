# Templates de Questionários Socioeconômicos

Este diretório contém os templates de perguntas padrão para os diferentes tipos de formulários socioeconômicos.

## Estrutura dos Arquivos

Cada arquivo JSON contém:

- `formType`: Tipo do formulário (aluno-jovem, aluno-velho, professor, diretor, secretario)
- `title`: Título do questionário
- `description`: Descrição do questionário
- `questions`: Array com as perguntas do questionário

## Templates Disponíveis

### aluno_jovem_questions.json

Questionário para alunos da **Educação Infantil** e **Anos Iniciais** (1º ao 5º ano).

**Segmentos atendidos:**

- Creche
- Pré I (Jardim 1)
- Pré II (Jardim 2)
- 1º Ano ao 5º Ano do Ensino Fundamental

**Perguntas principais:**

- q1: Curso/série atual (NOVA - adicionada para identificar distorção idade-série)
- q2: Idade (NOVA - com alternativas para análise de distorção)
- q3-q24: Perguntas baseadas no questionário SAEB 2023 do 5º ano

**Total de perguntas:** 24 (com múltiplas subperguntas nas questões de matriz)

### aluno_velho_questions.json

Questionário para alunos dos **Anos Finais** (4º ao 9º ano) e **EJA** (1º ao 9º Período).

**Segmentos atendidos:**

- 4º Ano ao 9º Ano do Ensino Fundamental
- EJA 1º ao 9º Período (Educação de Jovens e Adultos)

**Perguntas principais:**

- q1: Curso/série/ano atual (NOVA - inclui 15 opções: 4º ao 9º Ano + EJA 1º ao 9º Período)
- q2: Idade (NOVA - 13 anos ou menos até 18 anos ou mais)
- q3-q24: Perguntas baseadas no questionário SAEB 2023 do 9º ano
- q25: Planos futuros após Ensino Fundamental (NOVA - não existe no aluno-jovem)

**Total de perguntas:** 25 (com múltiplas subperguntas nas questões de matriz)

## Como Usar

### Criar um formulário com o template via API:

```python
import json

# Carregar o template
with open('app/socioeconomic_forms/templates/aluno_jovem_questions.json', 'r', encoding='utf-8') as f:
    template = json.load(f)

# Usar no payload da requisição
payload = {
    "title": template["title"],
    "description": template["description"],
    "formType": template["formType"],
    "questions": template["questions"],
    "targetGroups": ["alunos"],
    "selectedSchools": [...],
    "selectedGrades": [...],
    # ... outros campos necessários
}
```

### Estrutura de Perguntas

#### Tipos de perguntas suportados:

1. **selecao_unica**: Pergunta com uma única opção de resposta

    ```json
    {
    	"id": "q1",
    	"text": "Qual é o seu curso/série atual?",
    	"type": "selecao_unica",
    	"options": ["Creche", "Pré I", "..."],
    	"required": true,
    	"order": 1
    }
    ```

2. **matriz_selecao**: Pergunta com múltiplas subperguntas e mesmas opções

    ```json
    {
    	"id": "q6",
    	"text": "Você possui deficiência...",
    	"type": "matriz_selecao",
    	"subQuestions": [
    		{ "id": "q6a", "text": "Deficiência" },
    		{ "id": "q6b", "text": "Transtorno do espectro autista" }
    	],
    	"options": ["Não", "Sim"],
    	"required": true,
    	"order": 6
    }
    ```

3. **multipla_escolha**: Pergunta com múltiplas opções de resposta
4. **slider**: Pergunta com escala numérica
5. **slider_com_opcao**: Slider com opção adicional

## Análise de Distorção Idade-Série

As perguntas q1 (curso/série) e q2 (idade) permitem análise de distorção idade-série baseada nas tabelas:

### Tabela aluno-jovem (Educação Infantil e Anos Iniciais)

| Segmento      | Série/Ano | Idade Certa | Defasagem (1 ano) | Distorção (A partir de) |
| ------------- | --------- | ----------- | ----------------- | ----------------------- |
| Infantil      | Creche    | 0 a 3 anos  | 4 anos            | 5 anos                  |
| Infantil      | Pré I     | 4 anos      | 5 anos            | 6 anos                  |
| Infantil      | Pré II    | 5 anos      | 6 anos            | 7 anos                  |
| Anos Iniciais | 1º Ano    | 6 anos      | 7 anos            | 8 anos                  |
| Anos Iniciais | 2º Ano    | 7 anos      | 8 anos            | 9 anos                  |
| Anos Iniciais | 3º Ano    | 8 anos      | 9 anos            | 10 anos                 |
| Anos Iniciais | 4º Ano    | 9 anos      | 10 anos           | 11 anos                 |
| Anos Iniciais | 5º Ano    | 10 anos     | 11 anos           | 12 anos                 |

### Tabela aluno-velho (Anos Finais e EJA)

| Segmento      | Série/Ano/Período | Antes da Idade | Idade Certa | Defasagem (1 ano) | Distorção (A partir de) |
| ------------- | ----------------- | -------------- | ----------- | ----------------- | ----------------------- |
| Anos Iniciais | 4º Ano            | 8 anos         | 9 anos      | 10 anos           | 11 anos                 |
| Anos Iniciais | 5º Ano            | 9 anos         | 10 anos     | 11 anos           | 12 anos                 |
| Anos Finais   | 6º Ano            | 10 anos        | 11 anos     | 12 anos           | 13 anos                 |
| Anos Finais   | 7º Ano            | 11 anos        | 12 anos     | 13 anos           | 14 anos                 |
| Anos Finais   | 8º Ano            | 12 anos        | 13 anos     | 14 anos           | 15 anos                 |
| Anos Finais   | 9º Ano            | 13 anos        | 14 anos     | 15 anos           | 16 anos                 |
| EJA           | 1º ao 9º Período  | Incorreto < 15 | 15 anos +   | -                 | -                       |

## Notas Importantes

### aluno-jovem:

- ⚠️ **EJA NÃO está incluído**: Destinado apenas para Educação Infantil e Anos Iniciais
- ✅ Perguntas baseadas no questionário SAEB 2023 do 5º ano
- ✅ Total: 24 perguntas

### aluno-velho:

- ✅ **EJA ESTÁ incluído**: Destinado para Anos Finais (4º ao 9º ano) e EJA (1º ao 9º Período)
- ✅ Perguntas baseadas no questionário SAEB 2023 do 9º ano
- ✅ Total: 25 perguntas (inclui q25 sobre planos futuros)
- ✅ q1 tem 15 opções (6 anos + 9 períodos EJA)

### Geral:

- ✅ Todas as perguntas são obrigatórias (`required: true`)
- ✅ IDs seguem padrão sequencial (q1, q2, q3...) com sufixos para subperguntas (q6a, q6b...)

## Grupos de Perguntas

### aluno-jovem (24 perguntas):

1. **Perfil Demográfico** (q1-q5): Curso/série, idade, sexo, língua, raça
2. **Contexto Familiar e Socioeconômico** (q6-q14): Deficiência, família, escolaridade dos pais, bens domésticos
3. **Trajetória e Contexto Escolar** (q15-q21): Transporte, trajetória escolar, reprovação
4. **Percepções sobre o Ambiente Escolar** (q22-q24): Uso do tempo, práticas pedagógicas, percepções sobre a escola

### aluno-velho (25 perguntas):

1. **Perfil Demográfico** (q1-q5): Curso/série/ano, idade, sexo, língua, raça
2. **Contexto Familiar e Socioeconômico** (q6-q14): Deficiência, família, escolaridade dos pais, bens domésticos
3. **Trajetória e Contexto Escolar** (q15-q21): Transporte, trajetória escolar, reprovação
4. **Percepções sobre o Ambiente Escolar** (q22-q24): Uso do tempo, práticas pedagógicas, percepções sobre a escola
5. **Planos Futuros** (q25): Expectativas após conclusão do Ensino Fundamental
