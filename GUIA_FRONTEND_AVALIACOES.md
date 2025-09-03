# Guia para Frontend - Rota `/evaluation_results/avaliacoes`

## 📋 **Visão Geral**

A rota `/evaluation_results/avaliacoes` retorna dados completos de avaliações com **proficiência calculada por disciplina**, diferenciando corretamente entre Matemática e Português.

## 🔗 **Endpoint**

```
GET /evaluation_results/avaliacoes
```

## 📝 **Parâmetros Obrigatórios**

- `estado`: Estado (não pode ser 'all')
- `municipio`: Município
- `avaliacao`: ID da avaliação específica ou 'all'
- `escola`: ID da escola ou 'all'
- `serie`: ID da série ou 'all'
- `turma`: ID da turma ou 'all'
- `page`: Página (padrão: 1)
- `per_page`: Itens por página (padrão: 10, máximo: 100)

## 📊 **Estrutura da Resposta**

### 1. **`estatisticas_gerais`** - Dados Consolidados
```json
{
  "tipo": "avaliacao",
  "nome": "Avaliação Específica",
  "total_alunos": 2,
  "alunos_participantes": 2,
  "media_nota_geral": 6.67,
  "media_proficiencia_geral": 300.0,
  "distribuicao_classificacao_geral": {
    "abaixo_do_basico": 1,
    "basico": 0,
    "adequado": 0,
    "avancado": 1
  }
}
```

**Campos importantes:**
- `media_proficiencia_geral`: Média de proficiência de todas as disciplinas
- `distribuicao_classificacao_geral`: Distribuição consolidada

### 2. **`resultados_por_disciplina`** - Dados por Disciplina ⭐
```json
[
  {
    "disciplina": "Português",
    "media_proficiencia": 200.0,
    "media_nota": 5.0,
    "distribuicao_classificacao": {
      "abaixo_do_basico": 1,
      "basico": 0,
      "adequado": 0,
      "avancado": 1
    }
  },
  {
    "disciplina": "Matemática",
    "media_proficiencia": 425.0,
    "media_nota": 10.0,
    "distribuicao_classificacao": {
      "abaixo_do_basico": 0,
      "basico": 0,
      "adequado": 0,
      "avancado": 2
    }
  }
]
```

**Campos importantes:**
- `disciplina`: Nome da disciplina
- `media_proficiencia`: Média de proficiência específica da disciplina
- `media_nota`: Média de nota específica da disciplina
- `distribuicao_classificacao`: Distribuição por disciplina

### 3. **`tabela_detalhada`** - Dados Detalhados por Aluno ⭐
```json
{
  "disciplinas": [
    {
      "id": "disciplina-id",
      "nome": "Português",
      "questoes": [
        {
          "numero": 1,
          "habilidade": "Leitura e interpretação de textos",
          "codigo_habilidade": "LP1.1"
        }
      ],
      "alunos": [
        {
          "id": "aluno-id",
          "nome": "João Silva",
          "nivel_proficiencia": "Abaixo do Básico",
          "nota": 0.0,
          "proficiencia": 0.0,
          "total_acertos": 0,
          "respostas_por_questao": [
            {
              "questao": 1,
              "acertou": false,
              "respondeu": true,
              "resposta": "C"
            }
          ]
        }
      ]
    }
  ]
}
```

**Campos importantes:**
- `disciplinas[].alunos[].proficiencia`: Proficiência individual do aluno na disciplina
- `disciplinas[].alunos[].nivel_proficiencia`: Classificação do aluno na disciplina
- `disciplinas[].alunos[].respostas_por_questao`: Respostas detalhadas

### 4. **`ranking`** - Ranking dos Alunos
```json
[
  {
    "posicao": 1,
    "nome": "Maria Santos",
    "nota_geral": 10.0,
    "proficiencia_geral": 400.0,
    "classificacao_geral": "Avançado"
  }
]
```

### 5. **`resultados_detalhados`** - Dados por Avaliação
```json
{
  "avaliacoes": [
    {
      "id": "avaliacao-id",
      "titulo": "Avaliação de Matemática",
      "media_proficiencia": 300.0,
      "distribuicao_classificacao": {...}
    }
  ],
  "paginacao": {
    "page": 1,
    "per_page": 10,
    "total": 1,
    "total_pages": 1
  }
}
```

## 🎯 **Diferenciação por Disciplina**

### **Matemática vs Português**
- **Matemática**: Proficiência máxima 425, faixas de classificação específicas
- **Português**: Proficiência máxima 400, faixas de classificação diferentes

### **Exemplo de Diferenciação:**
```json
// Português
{
  "disciplina": "Português",
  "media_proficiencia": 200.0,  // Escala 0-400
  "distribuicao_classificacao": {
    "avancado": 1  // 200+ pontos
  }
}

// Matemática  
{
  "disciplina": "Matemática",
  "media_proficiencia": 425.0,  // Escala 0-425
  "distribuicao_classificacao": {
    "avancado": 2  // 350+ pontos
  }
}
```

## 📱 **Como Usar no Frontend**

### **1. Para Dashboard Geral:**
```javascript
// Usar estatisticas_gerais
const mediaGeral = response.estatisticas_gerais.media_proficiencia_geral;
const distribuicaoGeral = response.estatisticas_gerais.distribuicao_classificacao_geral;
```

### **2. Para Gráficos por Disciplina:**
```javascript
// Usar resultados_por_disciplina
response.resultados_por_disciplina.forEach(disciplina => {
  console.log(`${disciplina.disciplina}: ${disciplina.media_proficiencia}`);
});
```

### **3. Para Tabela Detalhada:**
```javascript
// Usar tabela_detalhada
response.tabela_detalhada.disciplinas.forEach(disciplina => {
  disciplina.alunos.forEach(aluno => {
    console.log(`${aluno.nome}: ${aluno.proficiencia} (${aluno.nivel_proficiencia})`);
  });
});
```

### **4. Para Ranking:**
```javascript
// Usar ranking
response.ranking.forEach(aluno => {
  console.log(`${aluno.posicao}º ${aluno.nome}: ${aluno.proficiencia_geral}`);
});
```

## ⚠️ **Pontos Importantes**

1. **Proficiência por Disciplina**: Cada disciplina tem sua própria escala de proficiência
2. **Classificação Diferenciada**: Matemática e Português têm faixas de classificação diferentes
3. **Dados Consolidados**: `estatisticas_gerais` contém médias de todas as disciplinas
4. **Dados Específicos**: `resultados_por_disciplina` contém dados específicos de cada disciplina
5. **Dados Individuais**: `tabela_detalhada` contém dados de cada aluno por disciplina

## 🔍 **Exemplo de Uso Completo**

```javascript
// Fazer requisição
const response = await fetch('/evaluation_results/avaliacoes?estado=Rondônia&municipio=Jaru&avaliacao=123');

// Processar dados
const data = await response.json();

// Dashboard geral
const mediaGeral = data.estatisticas_gerais.media_proficiencia_geral;

// Gráfico por disciplina
const disciplinas = data.resultados_por_disciplina.map(d => ({
  nome: d.disciplina,
  proficiencia: d.media_proficiencia
}));

// Tabela de alunos
const alunos = data.tabela_detalhada.disciplinas.flatMap(d => 
  d.alunos.map(aluno => ({
    nome: aluno.nome,
    disciplina: d.nome,
    proficiencia: aluno.proficiencia,
    classificacao: aluno.nivel_proficiencia
  }))
);
```

## 📄 **Arquivo de Exemplo**

Veja o arquivo `exemplo_resposta_frontend.json` para um exemplo completo da resposta da API.
