# 📋 Mudanças Necessárias no Frontend - Cartões Resposta

## ✅ IMPLEMENTAÇÃO CONCLUÍDA NO BACKEND

### **O que foi mudado:**

1. **Geração de PDFs**: Agora gera **1 PDF por turma** com múltiplas páginas (1 página por aluno)
2. **Múltiplos escopos**: Suporta geração para 1 turma, múltiplas turmas de uma série ou escola inteira
3. **Estrutura de blocos e alternativas**: **MANTIDA** (não mudou nada)
4. **Batch de gabaritos**: Múltiplos gabaritos podem ser agrupados em um batch
5. **ZIP hierárquico**: Para escola, organiza PDFs em pastas por série

---

## 🔄 MUDANÇAS NECESSÁRIAS NO FRONTEND

### **1. Rota POST `/answer-sheets/generate` (MODIFICADA)**

#### **ANTES (apenas turma):**

```typescript
POST /answer-sheets/generate
{
  "class_id": "uuid",
  "num_questions": 48,
  "use_blocks": true,
  "blocks_config": {...},
  "correct_answers": {"1": "A", "2": "B", ...},
  "questions_options": {...},
  "test_data": {...}
}
```

#### **AGORA (3 escopos possíveis):**

**ESCOPO 1 - Uma turma (mesmo formato anterior):**

```typescript
POST /answer-sheets/generate
{
  "class_id": "uuid",  // ← Mantém este campo
  "num_questions": 48,
  "use_blocks": true,
  "blocks_config": {...},
  "correct_answers": {"1": "A", "2": "B", ...},
  "questions_options": {...},
  "test_data": {...}
}
```

**ESCOPO 2 - Todas turmas de uma série (NOVO):**

```typescript
POST /answer-sheets/generate
{
  "grade_id": "uuid",    // ← NOVO
  "school_id": "uuid",   // ← NOVO (obrigatório com grade_id)
  "num_questions": 48,
  "use_blocks": true,
  "blocks_config": {...},
  "correct_answers": {"1": "A", "2": "B", ...},
  "questions_options": {...},
  "test_data": {...}
}
```

**ESCOPO 3 - Todas turmas da escola (NOVO):**

```typescript
POST /answer-sheets/generate
{
  "school_id": "uuid",  // ← NOVO (sem grade_id = toda escola)
  "num_questions": 48,
  "use_blocks": true,
  "blocks_config": {...},
  "correct_answers": {"1": "A", "2": "B", ...},
  "questions_options": {...},
  "test_data": {...}
}
```

---

### **2. Resposta da Rota `/generate` (MODIFICADA)**

#### **ANTES:**

```typescript
{
  "status": "processing",
  "task_id": "abc-123",
  "gabarito_id": "gab-1",
  "class_id": "class-1",
  "class_name": "Turma A",
  "num_questions": 48,
  "polling_url": "/answer-sheets/task/abc-123/status"
}
```

#### **AGORA:**

```typescript
{
  "status": "processing",
  "message": "Cartões de resposta sendo gerados em background (school: Escola Municipal). Use o task_id para verificar o status.",
  "task_id": "abc-123",
  "scope": "school",  // ← NOVO: 'class', 'grade' ou 'school'
  "scope_name": "Escola Municipal",  // ← NOVO
  "batch_id": "batch-uuid",  // ← NOVO: null se escopo for 'class'
  "gabarito_ids": ["gab-1", "gab-2", "gab-3"],  // ← NOVO: lista de IDs
  "classes_count": 8,  // ← NOVO
  "classes": [  // ← NOVO: lista de turmas
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
    // ... mais turmas
  ],
  "num_questions": 48,
  "polling_url": "/answer-sheets/task/abc-123/status"
}
```

**🔑 IMPORTANTE:**

- Se `scope === 'class'`: Gerou apenas 1 turma (comportamento antigo)
- Se `scope === 'grade'` ou `'school'`: Gerou múltiplas turmas (novo comportamento)

---

### **3. Rota GET `/answer-sheets/task/{task_id}/status` (MODIFICADA)**

A resposta quando a task é concluída agora retorna:

```typescript
{
  "status": "completed",
  "task_id": "abc-123",
  "result": {
    "success": true,
    "scope": "school",  // ← NOVO
    "batch_id": "batch-uuid",  // ← NOVO
    "gabarito_ids": ["gab-1", "gab-2", ...],  // ← NOVO
    "total_classes": 8,  // ← NOVO: quantidade de turmas
    "total_students": 240,  // ← NOVO: total de alunos
    "total_pdfs": 8,  // ← NOVO: quantidade de PDFs gerados
    "minio_url": "s3://...",
    "download_size_bytes": 15728640,
    "classes": [  // ← NOVO: detalhes de cada turma
      {
        "gabarito_id": "gab-1",
        "class_id": "class-1",
        "class_name": "Turma A",
        "grade_name": "6º Ano",
        "filename": "6º Ano - Turma A.pdf",
        "total_students": 30,
        "total_pages": 30
      },
      // ... mais turmas
    ]
  }
}
```

---

### **4. Nova Rota: GET `/answer-sheets/batch/{batch_id}/download` (NOVO)**

Para baixar ZIP de um batch completo:

```typescript
GET /answer-sheets/batch/{batch_id}/download

Response:
{
  "download_url": "https://minio.com/presigned-url",  // URL pré-assinada (1 hora)
  "expires_in": "1 hour",
  "batch_id": "batch-uuid",
  "classes_count": 8,
  "classes": [
    {
      "gabarito_id": "gab-1",
      "class_id": "class-1",
      "class_name": "Turma A",
      "grade_name": "6º Ano",
      "school_name": "Escola Municipal"
    },
    // ... mais turmas
  ],
  "title": "Cartão Resposta",
  "num_questions": 48,
  "generated_at": "2026-02-03T18:30:00",
  "created_at": "2026-02-03T18:25:00",
  "minio_url": "s3://..."
}
```

---

### **5. Rota GET `/answer-sheets/gabarito/{gabarito_id}/download` (MODIFICADA)**

Agora retorna informações adicionais:

```typescript
GET /answer-sheets/gabarito/{gabarito_id}/download

Response:
{
  "download_url": "https://minio.com/presigned-url",
  "expires_in": "1 hour",
  "gabarito_id": "gab-1",
  "test_id": "test-1",
  "class_id": "class-1",
  "class_name": "Turma A",
  "title": "Cartão Resposta",
  "num_questions": 48,
  "generated_at": "2026-02-03T18:30:00",
  "created_at": "2026-02-03T18:25:00",
  "minio_url": "s3://...",
  "is_batch": true,  // ← NOVO: indica se faz parte de um batch
  "batch_id": "batch-uuid"  // ← NOVO: ID do batch (se houver)
}
```

**🔑 IMPORTANTE:**

- Se `is_batch === true`: O ZIP contém múltiplas turmas, não só esta
- Use `batch_id` para baixar o batch completo via `/batch/{batch_id}/download`

---

## 🎨 SUGESTÕES DE UI/UX

### **1. Tela de Geração de Cartões**

Adicione opções para escolher o escopo:

```typescript
// Componente exemplo
<Select onChange={handleScopeChange}>
  <option value="class">Gerar para uma turma</option>
  <option value="grade">Gerar para todas turmas de uma série</option>
  <option value="school">Gerar para toda a escola</option>
</Select>

{scope === 'class' && (
  <Select placeholder="Selecione a turma">
    {/* Lista de turmas */}
  </Select>
)}

{scope === 'grade' && (
  <>
    <Select placeholder="Selecione a série">
      {/* Lista de séries */}
    </Select>
    <Select placeholder="Selecione a escola">
      {/* Lista de escolas */}
    </Select>
  </>
)}

{scope === 'school' && (
  <Select placeholder="Selecione a escola">
    {/* Lista de escolas */}
  </Select>
)}
```

### **2. Progresso da Geração**

Para escopos múltiplos, mostre progresso por turma:

```typescript
// Durante polling
if (response.result?.classes) {
  const progress = {
    total: response.result.total_classes,
    current: response.result.classes.length,
    percentage: (response.result.classes.length / response.result.total_classes) * 100
  };

  return (
    <div>
      <ProgressBar value={progress.percentage} />
      <p>Gerando turma {progress.current} de {progress.total}</p>
      <ul>
        {response.result.classes.map(cls => (
          <li key={cls.gabarito_id}>
            ✅ {cls.grade_name} - {cls.class_name} ({cls.total_students} alunos)
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### **3. Download do ZIP**

Após conclusão, mostre opções de download:

```typescript
// Se for batch
if (response.result.batch_id) {
  return (
    <div>
      <h3>Cartões gerados com sucesso!</h3>
      <p>{response.result.total_pdfs} PDFs gerados ({response.result.total_students} alunos)</p>

      {/* Botão principal */}
      <Button onClick={() => downloadBatch(response.result.batch_id)}>
        📥 Baixar ZIP Completo ({formatBytes(response.result.download_size_bytes)})
      </Button>

      {/* Detalhes */}
      <Accordion>
        <AccordionItem title="Ver turmas geradas">
          <ul>
            {response.result.classes.map(cls => (
              <li key={cls.gabarito_id}>
                {cls.filename} - {cls.total_students} alunos
              </li>
            ))}
          </ul>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
```

---

## 📦 ESTRUTURA DO ZIP BAIXADO

### **Escopo: Uma turma (`scope: 'class'`)**

```
cartoes_[gabarito_id].zip
└── 6º Ano - Turma A.pdf  (30 páginas, 1 por aluno)
```

### **Escopo: Série (`scope: 'grade'`)**

```
cartoes_[batch_id].zip
├── 6º Ano - Turma A.pdf  (30 páginas)
├── 6º Ano - Turma B.pdf  (28 páginas)
└── 6º Ano - Turma C.pdf  (32 páginas)
```

### **Escopo: Escola (`scope: 'school'`)**

```
cartoes_[batch_id].zip
├── 6º Ano/
│   ├── 6º Ano - Turma A.pdf  (30 páginas)
│   └── 6º Ano - Turma B.pdf  (28 páginas)
├── 7º Ano/
│   ├── 7º Ano - Turma A.pdf  (25 páginas)
│   └── 7º Ano - Turma B.pdf  (27 páginas)
└── 8º Ano/
    └── 8º Ano - Turma A.pdf  (22 páginas)
```

---

## ⚠️ COMPATIBILIDADE

### **Código Antigo CONTINUA FUNCIONANDO ✅**

Se o frontend continuar enviando apenas `class_id`, funciona normalmente:

```typescript
// ✅ FUNCIONA (modo compatibilidade)
POST /answer-sheets/generate
{
  "class_id": "uuid",
  "num_questions": 48,
  // ... demais campos
}

Response:
{
  "status": "processing",
  "task_id": "abc-123",
  "scope": "class",  // ← Detecta automaticamente
  "batch_id": null,   // ← null para turma única
  "gabarito_ids": ["gab-1"],
  "classes_count": 1,
  // ... demais campos
}
```

---

## 🔑 RESUMO DAS MUDANÇAS

| Item                                              | Status          | Ação Frontend                         |
| ------------------------------------------------- | --------------- | ------------------------------------- |
| **Rota `/generate` aceita `grade_id`**            | ✅ Implementado | **Adicionar** seleção de série        |
| **Rota `/generate` aceita `school_id`**           | ✅ Implementado | **Adicionar** seleção de escola       |
| **Resposta com `scope`, `batch_id`, `classes[]`** | ✅ Implementado | **Adaptar** parsing da resposta       |
| **Nova rota `/batch/{id}/download`**              | ✅ Implementado | **Adicionar** botão de download batch |
| **Campo `is_batch` em `/gabarito/{id}/download`** | ✅ Implementado | **Verificar** se é batch              |
| **Estrutura de blocos e alternativas**            | ✅ Mantida      | **NENHUMA** mudança necessária        |
| **Formato de `blocks_config`**                    | ✅ Mantido      | **NENHUMA** mudança necessária        |

---

## 📝 MIGRATION

Execute manualmente:

```bash
cd migrations/versions
# A migration foi criada: 20260203_fix_expected_tasks_nullable.py
# Execute:
flask db upgrade
```

Isso irá:

1. Tornar coluna `expected_tasks` NULLABLE (resolve erro atual)
2. Adicionar coluna `batch_id` na tabela `answer_sheet_gabaritos`

---

## 🎯 PRÓXIMOS PASSOS

1. **Atualizar frontend** conforme este documento
2. **Executar migration** no banco de dados
3. **Testar** geração de cartões para 1 turma (deve funcionar sem mudanças)
4. **Implementar UI** para seleção de escopo (série/escola)
5. **Testar** geração em batch (múltiplas turmas)

---

## 💡 DÚVIDAS?

- **P:** O formato dos blocos mudou?
  **R:** NÃO. Blocos numerados, por disciplina e alternativas variáveis continuam iguais.

- **P:** Preciso mudar algo no envio de `blocks_config`?
  **R:** NÃO. O formato é o mesmo.

- **P:** O sistema de correção precisa mudar?
  **R:** NÃO. Cada página do PDF tem QR code único, a correção funciona igual.

- **P:** Posso continuar gerando apenas para 1 turma?
  **R:** SIM. Basta enviar `class_id` como antes.

---

## ✨ FIM

Todas as mudanças foram implementadas no backend. O frontend precisa apenas adaptar para os novos escopos (opcional) e ajustar o parsing das respostas.
