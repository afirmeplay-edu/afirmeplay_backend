# 📚 Exemplos de Uso - Blocos por Disciplinas em Cartões Resposta

Este documento mostra como o **frontend** deve enviar os dados para gerar cartões resposta com blocos separados por disciplinas.

---

## 🎯 **CENÁRIO 1: SEM DISCIPLINAS (Comportamento Original)**

Se você **NÃO** quiser separar por disciplinas, basta enviar como antes:

### **Exemplo: 48 questões em 4 blocos automáticos**

```javascript
const requestBody = {
  class_id: "abc-123-def-456",
  num_questions: 48,
  use_blocks: true,
  blocks_config: {
    use_blocks: true,
    num_blocks: 4,              // ✅ Sistema divide automaticamente
    questions_per_block: 12     // ✅ 12 questões por bloco
  },
  correct_answers: {
    "1": "A",
    "2": "B",
    "3": "C",
    // ... até "48": "D"
  },
  test_data: {
    title: "Prova Mensal - Outubro",
    municipality: "São Paulo",
    state: "SP",
    grade_name: "5º Ano"
  }
};

// POST /answer-sheets/generate
fetch('/answer-sheets/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestBody)
});
```

**Resultado:** Sistema divide automaticamente em 4 blocos:
- Bloco 01: Questões 1-12
- Bloco 02: Questões 13-24
- Bloco 03: Questões 25-36
- Bloco 04: Questões 37-48

---

## 🎯 **CENÁRIO 2: COM DISCIPLINAS (Nova Funcionalidade)**

Se você quiser separar por disciplinas, envie a estrutura `blocks`:

### **Exemplo 1: 78 questões em 3 disciplinas**

```javascript
const requestBody = {
  class_id: "abc-123-def-456",
  num_questions: 78,
  use_blocks: true,
  blocks_config: {
    use_blocks: true,
    num_blocks: 3,
    blocks: [  // ✅ NOVO: Definir blocos manualmente
      {
        block_id: 1,
        subject_name: "Matemática",
        questions_count: 26,
        start_question: 1,
        end_question: 26
      },
      {
        block_id: 2,
        subject_name: "Português",
        questions_count: 26,
        start_question: 27,
        end_question: 52
      },
      {
        block_id: 3,
        subject_name: "Ciências",
        questions_count: 26,
        start_question: 53,
        end_question: 78
      }
    ]
  },
  correct_answers: {
    "1": "A",   // Matemática Q1
    "2": "B",   // Matemática Q2
    // ...
    "26": "C",  // Matemática Q26
    "27": "A",  // Português Q1
    // ...
    "78": "D"   // Ciências Q26
  },
  questions_options: {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"],  // Questão com 3 alternativas
    "3": ["A", "B", "C", "D"],
    // ... (opcional, se não enviar usa padrão A,B,C,D)
  },
  test_data: {
    title: "Prova Bimestral - Multidisciplinar",
    municipality: "Rio de Janeiro",
    state: "RJ",
    grade_name: "9º Ano"
  }
};

// POST /answer-sheets/generate
fetch('/answer-sheets/generate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(requestBody)
});
```

**Resultado no Cartão Resposta:**
```
┌─────────────────────────┐
│     MATEMÁTICA          │
│  Q1  [A][B][C][D]       │
│  Q2  [A][B][C][D]       │
│  ...                    │
│  Q26 [A][B][C][D]       │
└─────────────────────────┘

┌─────────────────────────┐
│     PORTUGUÊS           │
│  Q27 [A][B][C][D]       │
│  Q28 [A][B][C][D]       │
│  ...                    │
│  Q52 [A][B][C][D]       │
└─────────────────────────┘

┌─────────────────────────┐
│     CIÊNCIAS            │
│  Q53 [A][B][C][D]       │
│  Q54 [A][B][C][D]       │
│  ...                    │
│  Q78 [A][B][C][D]       │
└─────────────────────────┘
```

---

### **Exemplo 2: 104 questões em 4 disciplinas (Máximo)**

```javascript
const requestBody = {
  class_id: "abc-123-def-456",
  num_questions: 104,  // Máximo permitido
  use_blocks: true,
  blocks_config: {
    use_blocks: true,
    num_blocks: 4,  // Máximo permitido
    blocks: [
      {
        block_id: 1,
        subject_name: "Matemática",
        questions_count: 26,  // Máximo por bloco
        start_question: 1,
        end_question: 26
      },
      {
        block_id: 2,
        subject_name: "Português",
        questions_count: 26,
        start_question: 27,
        end_question: 52
      },
      {
        block_id: 3,
        subject_name: "Ciências",
        questions_count: 26,
        start_question: 53,
        end_question: 78
      },
      {
        block_id: 4,
        subject_name: "História",
        questions_count: 26,
        start_question: 79,
        end_question: 104
      }
    ]
  },
  correct_answers: {
    "1": "A",
    // ... todas as 104 respostas
    "104": "D"
  },
  test_data: {
    title: "Provão - 4 Disciplinas",
    municipality: "Belo Horizonte",
    state: "MG",
    grade_name: "8º Ano"
  }
};
```

---

### **Exemplo 3: Blocos com tamanhos diferentes**

```javascript
const requestBody = {
  class_id: "abc-123-def-456",
  num_questions: 60,
  use_blocks: true,
  blocks_config: {
    use_blocks: true,
    num_blocks: 3,
    blocks: [
      {
        block_id: 1,
        subject_name: "Matemática",
        questions_count: 20,  // ✅ Bloco menor
        start_question: 1,
        end_question: 20
      },
      {
        block_id: 2,
        subject_name: "Português",
        questions_count: 25,  // ✅ Tamanho diferente
        start_question: 21,
        end_question: 45
      },
      {
        block_id: 3,
        subject_name: "Geografia",
        questions_count: 15,  // ✅ Outro tamanho
        start_question: 46,
        end_question: 60
      }
    ]
  },
  correct_answers: {
    "1": "A",
    // ...
    "60": "C"
  },
  test_data: {
    title: "Prova Customizada",
    municipality: "Curitiba",
    state: "PR",
    grade_name: "7º Ano"
  }
};
```

---

## ⚠️ **VALIDAÇÕES DO BACKEND**

O backend valida automaticamente:

### ✅ **Validações de Blocos:**
- ❌ **Máximo 4 blocos**
- ❌ **Máximo 26 questões por bloco**
- ❌ **Máximo 104 questões no total** (4 × 26)

### ✅ **Validações de Sequência:**
- ✅ Questões devem ser sequenciais (1, 2, 3, ..., N)
- ✅ Sem lacunas entre blocos
- ✅ Soma das questões dos blocos = `num_questions`

### ✅ **Validações de Campos:**
- ✅ `subject_name` é obrigatório para cada bloco
- ✅ `start_question`, `end_question`, `questions_count` são obrigatórios
- ✅ Contagem consistente: `end - start + 1 = count`

---

## 🚫 **EXEMPLOS DE ERROS**

### **Erro 1: Mais de 4 blocos**

```javascript
blocks_config: {
  blocks: [
    { block_id: 1, subject_name: "Mat", questions_count: 20, start_question: 1, end_question: 20 },
    { block_id: 2, subject_name: "Port", questions_count: 20, start_question: 21, end_question: 40 },
    { block_id: 3, subject_name: "Ciê", questions_count: 20, start_question: 41, end_question: 60 },
    { block_id: 4, subject_name: "Hist", questions_count: 20, start_question: 61, end_question: 80 },
    { block_id: 5, subject_name: "Geo", questions_count: 20, start_question: 81, end_question: 100 }  // ❌
  ]
}
```

**Resposta:**
```json
{
  "error": "Máximo de 4 blocos permitidos. Você enviou 5 blocos."
}
```

---

### **Erro 2: Mais de 26 questões em um bloco**

```javascript
blocks_config: {
  blocks: [
    { 
      block_id: 1, 
      subject_name: "Matemática", 
      questions_count: 30,  // ❌ Máximo é 26
      start_question: 1, 
      end_question: 30 
    }
  ]
}
```

**Resposta:**
```json
{
  "error": "Bloco 1 (Matemática): máximo de 26 questões por bloco. Você definiu 30."
}
```

---

### **Erro 3: Soma das questões não bate**

```javascript
num_questions: 50,  // ❌ Total informado
blocks_config: {
  blocks: [
    { block_id: 1, subject_name: "Mat", questions_count: 20, start_question: 1, end_question: 20 },
    { block_id: 2, subject_name: "Port", questions_count: 25, start_question: 21, end_question: 45 }
    // Soma = 45, mas informou 50
  ]
}
```

**Resposta:**
```json
{
  "error": "Soma das questões dos blocos (45) difere do total informado (50)."
}
```

---

### **Erro 4: Questões não sequenciais**

```javascript
blocks_config: {
  blocks: [
    { block_id: 1, subject_name: "Mat", questions_count: 20, start_question: 1, end_question: 20 },
    { block_id: 2, subject_name: "Port", questions_count: 20, start_question: 25, end_question: 44 }  // ❌ Deveria começar em 21
  ]
}
```

**Resposta:**
```json
{
  "error": "Bloco 2 (Port): deveria começar na questão 21, mas começa em 25."
}
```

---

## 📊 **RESUMO COMPARATIVO**

| Aspecto | Sem Disciplinas | Com Disciplinas |
|---------|----------------|-----------------|
| **Estrutura `blocks_config`** | `num_blocks` + `questions_per_block` | Array `blocks` com disciplinas |
| **Distribuição** | ✅ Automática | ✅ Manual |
| **Nome dos blocos** | "BLOCO 01", "BLOCO 02", ... | "MATEMÁTICA", "PORTUGUÊS", ... |
| **Flexibilidade** | ❌ Todos blocos iguais | ✅ Blocos de tamanhos diferentes |
| **Complexidade** | 🟢 Simples | 🟡 Média |

---

## 🎯 **RECOMENDAÇÕES**

### **Use SEM disciplinas quando:**
- ✅ Todas as questões têm o mesmo peso/importância
- ✅ Não há necessidade de separação temática
- ✅ Quer simplicidade máxima

### **Use COM disciplinas quando:**
- ✅ Prova multidisciplinar (Matemática, Português, Ciências, etc.)
- ✅ Quer identificação visual clara de cada matéria no cartão
- ✅ Precisa de blocos com tamanhos diferentes
- ✅ Quer organização por tema/disciplina

---

## 💡 **DICA: Como construir o request no Frontend**

```javascript
// Função helper para construir blocos por disciplinas
function buildBlocksConfig(subjects) {
  let currentQuestion = 1;
  const blocks = [];
  
  subjects.forEach((subject, index) => {
    const questionsCount = subject.questionsCount;
    const startQuestion = currentQuestion;
    const endQuestion = currentQuestion + questionsCount - 1;
    
    blocks.push({
      block_id: index + 1,
      subject_name: subject.name,
      questions_count: questionsCount,
      start_question: startQuestion,
      end_question: endQuestion
    });
    
    currentQuestion = endQuestion + 1;
  });
  
  return {
    use_blocks: true,
    num_blocks: blocks.length,
    blocks: blocks
  };
}

// Uso:
const subjects = [
  { name: "Matemática", questionsCount: 26 },
  { name: "Português", questionsCount: 26 },
  { name: "Ciências", questionsCount: 26 }
];

const blocksConfig = buildBlocksConfig(subjects);
// Resultado:
// {
//   use_blocks: true,
//   num_blocks: 3,
//   blocks: [
//     { block_id: 1, subject_name: "Matemática", questions_count: 26, start_question: 1, end_question: 26 },
//     { block_id: 2, subject_name: "Português", questions_count: 26, start_question: 27, end_question: 52 },
//     { block_id: 3, subject_name: "Ciências", questions_count: 26, start_question: 53, end_question: 78 }
//   ]
// }
```

---

## ✅ **CHECKLIST FINAL**

Antes de enviar o request, verifique:

- [ ] `num_questions` está correto
- [ ] Soma de `questions_count` de todos blocos = `num_questions`
- [ ] Máximo 4 blocos
- [ ] Máximo 26 questões por bloco
- [ ] Questões são sequenciais (sem lacunas)
- [ ] Cada bloco tem `subject_name`
- [ ] `start_question` e `end_question` estão corretos
- [ ] `correct_answers` tem todas as questões (1 até `num_questions`)

---

**🎉 Pronto! Agora você pode gerar cartões resposta com blocos separados por disciplinas!**
