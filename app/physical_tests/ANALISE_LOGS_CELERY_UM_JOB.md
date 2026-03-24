# Análise dos logs do Celery: um job, vários itens (não uma task por aluno)

**Objetivo:** Esclarecer o que os logs mostram — uma única task Celery com atualizações de progresso por aluno, não uma task por aluno.

---

## 1. O que os logs mostram

Trecho que você compartilhou (resumido):

1. **20:35:25** — 3x `Arquivo baixado do MinIO: question-images/...`
2. **20:35:26** — WeasyPrint: `Ignored clip-path: polygon(...)` (2 ocorrências, linhas 237 e 261)
3. **20:35:29** — WeasyPrint: mesmo `clip-path` (2 ocorrências)
4. **20:36:52** — `✅ Job 7680baeb-8fe1-4225-ab9a-8e0eb54bb4d2: Item 0 concluído - ALICE LIMA DA SILVA`
5. **20:36:52** — WeasyPrint: `clip-path` (2 ocorrências)
6. **20:38:15** — `✅ Job 7680baeb-8fe1-4225-ab9a-8e0eb54bb4d2: Item 1 concluído - ANTÔNIO MARCOS SILVA AQUINO`
7. **20:38:16** — WeasyPrint: `clip-path` (2 ocorrências)
8. **20:39:40** — `✅ Job 7680baeb-8fe1-4225-ab9a-8e0eb54bb4d2: Item 2 concluído - BERNARDO CAVALCANTE SILVA`
9. **20:39:40** — WeasyPrint: `clip-path` (2 ocorrências)

O **job_id é sempre o mesmo:** `7680baeb-8fe1-4225-ab9a-8e0eb54bb4d2`.  
Os “Item 0”, “Item 1”, “Item 2” são **índices de um único job**, não IDs de tasks diferentes.

---

## 2. De onde vêm “Item N concluído” no código

- **Arquivo:** `app/services/progress_store.py`  
- **Função:** `update_item_done(job_id, index, result)`  
- **Log:** `logger.info(f"✅ Job {job_id}: Item {index} concluído - {result.get('student_name', 'N/A')}")` (linha 215)

Ou seja: “Item N concluído” é apenas o progress_store marcando o **item N** do **mesmo job** como concluído.

Quem chama `update_item_done` para esse fluxo:

- **Arquivo:** `app/services/institutional_test_weasyprint_generator.py`  
- **Função:** `generate_institutional_test_pdf_arch4()`  
- **Trecho:** dentro do `for idx, student in enumerate(students_data, 1):`, após gerar o PDF do aluno, merge e gravar em disco (linhas 334–342):

```python
if job_id:
    try:
        from app.services.progress_store import update_item_done
        update_item_done(job_id, index_0, {
            'student_id': student_id,
            'student_name': student.get('name', student.get('nome', '')),
            ...
        })
```

Ou seja: **uma única execução** de `generate_institutional_test_pdf_arch4()` (uma única task Celery) percorre todos os alunos e, a cada aluno finalizado, chama `update_item_done(job_id, index_0, ...)`. Por isso você vê o **mesmo** `job_id` para Item 0, 1, 2 — é o mesmo processo, mesmo job.

---

## 3. Quem cria o job_id (uma vez por geração)

- **Arquivo:** `app/physical_tests/tasks.py`  
- **Função:** `generate_physical_forms_async`  
- **Trecho:** antes de chamar o form service (por volta das linhas 356–359):

```python
from app.services.progress_store import create_job, complete_job
create_job(job_id=job_id, total=len(students_data), test_id=test_id)
test_data['job_id'] = job_id
```

O `job_id` é o `self.request.id` da **única** task Celery (`generate_physical_forms_async`). Esse mesmo `job_id` é passado em `test_data` para `PhysicalTestFormService.generate_physical_forms()` e depois para `generate_institutional_test_pdf_arch4()`. Portanto: **1 task Celery → 1 job_id → N itens (alunos)**.

---

## 4. Interpretação da linha do tempo dos seus logs

| Fase | Horário | O que é (no código arch4) |
|------|---------|---------------------------|
| Início da task | — | Task `generate_physical_forms_async` inicia; `create_job(job_id, total=…)`; chama form_service → gerador. |
| Inline de imagens | 20:35:25 | Dentro de `generate_institutional_test_pdf_arch4()`, **antes** do loop: preparação das questões e `_inline_question_images_html()` → 3 downloads do MinIO (3 imagens da prova). |
| PDF base (capa + questões) | 20:35:26 – 20:35:29 | Uma única renderização WeasyPrint do HTML da prova completa → avisos `clip-path` (2 no CSS, possivelmente repetidos em mais de uma página). |
| Aluno 0 (Alice) | 20:35:29 → 20:36:52 | Loop: renderização WeasyPrint **só da página OMR** de Alice, merge base + OMR, gravação do PDF, `update_item_done(job_id, 0, …)` → log “Item 0 concluído”. (~83 s) |
| Aluno 1 (Antônio) | 20:36:52 → 20:38:15 | Mesmo processo para o próximo aluno → “Item 1 concluído”. (~83 s) |
| Aluno 2 (Bernardo) | 20:38:15 → 20:39:40 | Mesmo processo → “Item 2 concluído”. (~85 s) |

Conclusão da linha do tempo:

- Os **3 downloads do MinIO** ocorrem **uma vez** no início (fase de inline das questões do PDF base).
- O **mesmo job_id** aparece em todos os “Item N concluído” → **uma única task Celery**.
- O tempo grande entre cada “Item N concluído” (~80 s) é o custo de, **por aluno**, renderizar só a página OMR com WeasyPrint, fazer o merge e gravar o PDF — sem novo download do MinIO nesse loop.

---

## 5. Resposta direta à sua conclusão

Você escreveu: *“o app não está usando esse código pois no log do celery há uma task por aluno”*.

- **Não há “uma task por aluno” nos logs.** Há **uma task** (um worker, um `request.id` = um `job_id`) que processa **vários alunos** em sequência e, a cada aluno, atualiza o progresso com `update_item_done(job_id, index, …)`. Por isso você vê “Item 0”, “Item 1”, “Item 2” com o **mesmo** `7680baeb-8fe1-4225-ab9a-8e0eb54bb4d2`.
- O **código em uso é exatamente o que analisamos:** `generate_physical_forms_async` (uma task) → `PhysicalTestFormService.generate_physical_forms()` → `InstitutionalTestWeasyPrintGenerator.generate_institutional_test_pdf_arch4()` (um loop por aluno, um job_id, `update_item_done` por aluno).
- Os logs batem com arch4: MinIO no início (inline uma vez), WeasyPrint do base uma vez, depois WeasyPrint da OMR por aluno e “Item N concluído” a cada aluno, sempre com o mesmo job_id.

Ou seja: **o app está usando esse código;** o que os logs mostram é **um job com vários itens (alunos)**, não várias tasks.

---

## 6. Se quiser confirmar no Celery

- No Celery, para essa geração, deve aparecer **uma única** task `physical_test_tasks.generate_physical_forms_async` por execução da geração (por exemplo, uma por clique em “Gerar formulários”).
- O `job_id` que você vê no progress_store (`7680baeb-...`) costuma ser o mesmo que o **task id** do Celery (`self.request.id` na task). Verifique no painel do Celery / Flower se há uma task por aluno ou uma task por prova; o código só enfileira **uma** task por prova.

Nenhum código foi alterado; esta análise apenas interpreta os logs e o código existente.
