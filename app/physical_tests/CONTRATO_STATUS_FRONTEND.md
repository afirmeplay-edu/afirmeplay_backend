# Contrato da rota de status – Geração de formulários físicos

**Endpoint:** `GET /physical-tests/task/<task_id>/status`

Este documento descreve a resposta do polling de status, em especial os campos **novos ou alterados** que o frontend pode usar.

---

## Resposta (estrutura geral)

A resposta mantém os campos já existentes. Abaixo, os que importam para o frontend.

### Campos existentes (sem mudança de contrato)

- `task_id`, `status`, `message`, `progress` (current, total, percentage)
- `summary` (total_classes, completed_classes, total_students, zip_minio_url, can_download, etc.)
- `classes` (array por turma: class_id, class_name, school_name, status, total_students, completed, successful, failed, errors)
- `errors` (lista de erros por aluno)

### Comportamento alterado (sem quebrar contrato)

1. **`classes` desde o primeiro GET**  
   As turmas passam a vir preenchidas logo no início da geração (class_id, class_name, school_name, total_students por turma). Não aparece mais uma única “Turma não informada” com o total geral; cada turma aparece separada com sua contagem correta.

2. **`message` dinâmico**  
   O campo `message` reflete a etapa atual do processamento (ex.: “Gerando turma C…”, “Salvando arquivos no banco de dados…”, “Criando pacote para download…”, “Enviando arquivos para o servidor…”, “Concluído”). O frontend pode usar só o `message` para exibir o texto ao usuário.

---

## Novos campos (contrato com o frontend)

O frontend **pode** usar estes campos para melhorar a UX (ex.: ícone ou label por etapa).

| Campo   | Tipo   | Sempre presente? | Descrição |
|--------|--------|------------------|-----------|
| `phase` | string | Não (só quando há job) | Indica a etapa atual. Valores possíveis: `"generating"`, `"saving"`, `"zipping"`, `"uploading"`, `"done"`. Útil para mostrar ícone/label diferente por fase (ex.: após 100% ainda mostrar “Enviando arquivos…” enquanto `phase === "uploading"`). |

### Valores de `phase`

- **`generating`** – Gerando PDFs (por turma/aluno). Inclui mensagens do tipo “Gerando turma X…”.
- **`saving`** – Salvando arquivos no banco de dados.
- **`zipping`** – Criando o pacote ZIP para download (progresso já pode estar em 100%).
- **`uploading`** – Enviando o ZIP para o servidor (progresso já pode estar em 100%).
- **`done`** – Processo concluído (quando o job é finalizado com sucesso).

Se `phase` não vier na resposta (ex.: job ainda não criado), o frontend pode continuar usando apenas `status` e `message` como hoje.

---

## Sugestão de uso no frontend

1. **Lista de turmas**  
   Usar `classes` desde o primeiro polling: mostrar quantidade de turmas, alunos por turma e qual turma está “em processamento” (item com `status === "processing"`).

2. **Evitar “travou” após 100%**  
   Quando `progress.percentage === 100` e `status === "processing"`, exibir o `message` atual (ex.: “Criando pacote para download…”, “Enviando arquivos para o servidor…”). Opcionalmente usar `phase` para escolher ícone ou cor por etapa.

3. **Download**  
   Habilitar o botão de download quando `summary.can_download === true` e, se desejar, quando `phase === "done"` (para consistência).

---

## Exemplo de resposta (durante geração, com turmas desde o início)

```json
{
  "task_id": "4891853e-474c-4ae1-81cf-8a393a922b8d",
  "status": "processing",
  "message": "Gerando turma C...",
  "phase": "generating",
  "progress": { "current": 2, "total": 96, "percentage": 2 },
  "summary": {
    "total_classes": 2,
    "total_students": 96,
    "completed_classes": 0,
    "can_download": false,
    "zip_minio_url": null
  },
  "classes": [
    {
      "class_id": "40ebe8c2-e875-4e1f-8ccd-1eae4dbda373",
      "class_name": "C",
      "school_name": "ESCOLA MUNICIPAL PEDRO ABILIO MADEIRO",
      "status": "processing",
      "total_students": 6,
      "completed": 2,
      "successful": 2,
      "failed": 0,
      "errors": []
    },
    {
      "class_id": "outro-uuid",
      "class_name": "D",
      "school_name": "MESMA ESCOLA",
      "status": "pending",
      "total_students": 90,
      "completed": 0,
      "successful": 0,
      "failed": 0,
      "errors": []
    }
  ],
  "errors": null
}
```

---

## Resumo para atualizar o frontend

- **Opcional:** ler e exibir `phase` para diferenciar etapas (principalmente após 100%: zipping/uploading).
- **Recomendado:** usar o `message` dinâmico quando `progress.percentage === 100` e ainda `status === "processing"`, para não dar impressão de travamento.
- **Recomendado:** usar `classes` desde o primeiro GET para mostrar turmas, alunos por turma e turma em processamento; não depender de “Turma não informada” com total geral.

Nenhum campo existente foi removido ou renomeado; apenas `phase` foi adicionado e `message`/`classes` passam a ser preenchidos de forma mais rica desde o início.
