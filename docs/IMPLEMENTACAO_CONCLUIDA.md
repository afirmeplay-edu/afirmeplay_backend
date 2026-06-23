# ✅ IMPLEMENTAÇÃO CONCLUÍDA: Edição de Estrutura do Cartão Resposta

## 📋 O Que Foi Implementado

### Nova Rota de API
```
PATCH /answer-sheets/gabarito/{gabarito_id}/structure
```

Permite editar:
- ✅ Quantidade de questões
- ✅ Quantidade e configuração de blocos
- ✅ Habilidades de cada questão
- ✅ Alternativas customizadas por questão

---

## 🎯 Contrato com o Frontend

### Endpoint
```
PATCH /answer-sheets/gabarito/{gabarito_id}/structure
```

### Headers Obrigatórios
```json
{
  "Authorization": "Bearer {jwt_token}",
  "Content-Type": "application/json",
  "X-City-Context": "{city_id}"
}
```

### Permissões Necessárias
- `admin`, `professor`, `coordenador`, `diretor` ou `tecadm`
- Apenas o **criador** pode editar o gabarito

---

## 📝 Request Body (Todos Opcionais)

### Estrutura Completa
```json
{
  "num_questions": 30,
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "uuid-da-disciplina",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      },
      {
        "block_id": 2,
        "subject_id": "uuid-da-disciplina-2",
        "subject_name": "Português",
        "start_question": 16,
        "end_question": 30,
        "questions_count": 15
      }
    ]
  },
  "question_skills": {
    "1": ["EF05MA01", "uuid-habilidade"],
    "2": ["EF05LP02"]
  },
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"]
  }
}
```

### Exemplo Simples (Apenas Quantidade)
```json
{
  "num_questions": 40
}
```

---

## 📊 Respostas da API

### ✅ Sucesso - Cartão NÃO Gerado (200)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "changes": {
    "num_questions": {"old": 20, "new": 30},
    "blocks_count": {"old": 2, "new": 3},
    "skills_updated": true
  }
}
```

### ⚠️ Sucesso - Cartão JÁ GERADO (200)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados não refletem as alterações. É necessário gerar os cartões novamente para que as mudanças apareçam nos documentos impressos.",
  "changes": {
    "num_questions": {"old": 20, "new": 30}
  }
}
```

### ❌ Bloqueado - Com Correções (422)
```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas. Editar agora poderia causar inconsistências nos resultados já calculados. Para fazer alterações, crie um novo cartão resposta.",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

### ❌ Erro de Validação (400)
```json
{
  "error": "Máximo de 4 blocos permitidos. Você enviou 5 blocos."
}
```

---

## 🔒 Regras de Negócio

| Estado do Cartão | Pode Editar? | Resposta |
|-----------------|--------------|----------|
| **Com correções existentes** | ❌ **NÃO** | Erro 422 + mensagem amigável |
| **Gerado mas não corrigido** | ✅ **SIM** | Sucesso 200 + **warning** sobre regenerar PDFs |
| **Apenas criado (não gerado)** | ✅ **SIM** | Sucesso 200 sem avisos |

---

## ✅ Validações Automáticas

O backend valida automaticamente:

| Validação | Regra |
|-----------|-------|
| Quantidade de questões | Min: 1, Max: 104 |
| Quantidade de blocos | Max: 4 blocos |
| Questões por bloco | Max: 26 questões |
| `subject_id` | Obrigatório em cada bloco |
| Soma de questões | Deve bater com `num_questions` |
| Sequência de questões | Devem ser sequenciais (1, 2, 3...) |
| Habilidades | Códigos convertidos para UUIDs |
| Disciplinas | Nomes resolvidos do banco se omitidos |

---

## 🔄 O Que o Backend Faz Automaticamente

1. ✅ Valida consistência entre blocos e total de questões
2. ✅ **Regenera coordenadas** (ROI das bolhas de resposta)
3. ✅ **Regenera topologia completa** da estrutura
4. ✅ Resolve códigos de habilidades (`EF05MA01` → UUID)
5. ✅ Resolve nomes de disciplinas se não enviados
6. ✅ **Ajusta `correct_answers`** se quantidade de questões mudou:
   - Questões removidas: descartadas
   - Questões novas: recebem valor padrão `"A"`
7. ✅ **Invalida templates** de blocos (força regeneração)
8. ✅ Detecta se tem correções (para bloquear)
9. ✅ Detecta se foi gerado (para avisar)

---

## 🎨 Implementação no Frontend

### 1️⃣ Verificar se Pode Editar

```javascript
async function canEditGabarito(gabaritoId) {
  // Verificar se tem correções
  const resultsResponse = await fetch(
    `/answer-sheets/results?gabarito_id=${gabaritoId}&page=1&per_page=1`,
    { headers: { 'Authorization': `Bearer ${token}`, 'X-City-Context': cityId } }
  );
  
  const resultsData = await resultsResponse.json();
  const hasCorrections = resultsData.total > 0;
  
  if (hasCorrections) {
    showError("Este cartão não pode ser editado porque já possui correções.");
    return false;
  }
  
  return true;
}
```

### 2️⃣ Enviar Edição

```javascript
async function editarEstrutura(gabaritoId, payload) {
  const response = await fetch(
    `/answer-sheets/gabarito/${gabaritoId}/structure`,
    {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'X-City-Context': cityId
      },
      body: JSON.stringify(payload)
    }
  );
  
  const data = await response.json();
  
  if (response.ok) {
    showSuccess(data.message);
    
    // Se tem warning, mostrar aviso sobre regenerar PDFs
    if (data.warning) {
      showWarningModal({
        title: "Edição realizada com sucesso!",
        message: data.warning,
        actions: [
          { label: "Gerar PDFs agora", onClick: () => navigateToGeneration(gabaritoId) },
          { label: "Entendido", onClick: () => closeModal() }
        ]
      });
    }
    
    return { success: true, data };
  } else if (response.status === 422) {
    // Bloqueado por correções
    showError(data.error);
    return { success: false, blocked: true };
  } else {
    // Erro de validação
    showError(data.error);
    return { success: false };
  }
}
```

### 3️⃣ Exemplo de Uso

```javascript
// Editar apenas quantidade
await editarEstrutura(gabaritoId, {
  num_questions: 40
});

// Editar blocos
await editarEstrutura(gabaritoId, {
  num_questions: 52,
  blocks_config: {
    blocks: [
      {
        block_id: 1,
        subject_id: "uuid-matematica",
        subject_name: "Matemática",
        start_question: 1,
        end_question: 26,
        questions_count: 26
      },
      {
        block_id: 2,
        subject_id: "uuid-portugues",
        subject_name: "Português",
        start_question: 27,
        end_question: 52,
        questions_count: 26
      }
    ]
  }
});

// Adicionar habilidades
await editarEstrutura(gabaritoId, {
  question_skills: {
    "1": ["EF05MA01", "EF05MA02"],
    "2": ["EF05LP01"]
  }
});
```

---

## 📚 Documentação Completa

Foram criados 3 arquivos de documentação:

1. **`docs/API_EDITAR_ESTRUTURA_CARTAO_RESPOSTA.md`**
   - Documentação completa da API
   - Todos os campos e validações
   - Exemplos de todos os casos de uso

2. **`docs/EXEMPLOS_TESTE_EDITAR_CARTAO.md`**
   - Exemplos práticos com `curl`
   - Scripts de teste em Python
   - Todos os cenários de teste

3. **`docs/RESUMO_CONTRATO_API_EDICAO.md`**
   - Resumo executivo
   - Quick reference para desenvolvedores
   - Tabelas comparativas

---

## 🔍 Status Codes

| Código | Significado |
|--------|------------|
| `200` | ✅ Edição realizada com sucesso |
| `400` | ❌ Erro de validação (dados inválidos) |
| `401` | ❌ Não autenticado |
| `403` | ❌ Sem permissão para editar |
| `404` | ❌ Gabarito não encontrado |
| `422` | ❌ Bloqueado por correções existentes |
| `500` | ❌ Erro interno do servidor |

---

## ⚡ Diferença Entre as Rotas de Edição

| Rota | O Que Edita | Recalcula Correções? |
|------|------------|---------------------|
| **`PATCH /gabarito/{id}/structure`** (NOVA) | Estrutura: questões, blocos, habilidades | ❌ NÃO |
| **`PATCH /gabaritos/{id}`** (EXISTENTE) | Apenas respostas corretas | ✅ SIM (automático) |

---

## ✨ Testes Realizados

✅ Arquivo sem erros de linting  
✅ Validações de campos implementadas  
✅ Lógica de bloqueio por correções  
✅ Lógica de aviso para cartões gerados  
✅ Regeneração de coordenadas  
✅ Regeneração de topologia  
✅ Ajuste automático de `correct_answers`

---

## 🚀 Próximos Passos (Frontend)

1. Criar interface de edição com formulário
2. Implementar validação client-side
3. Mostrar aviso visual quando cartão já foi gerado
4. Bloquear edição quando houver correções
5. Adicionar botão "Gerar PDFs" no modal de aviso
6. Testar fluxo completo: criar → editar → gerar → corrigir
