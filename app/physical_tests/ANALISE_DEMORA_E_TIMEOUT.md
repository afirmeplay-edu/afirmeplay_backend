# Análise: Por que está demorando tanto e por que deu timeout

**Contexto:** Geração de PDFs de provas físicas; após ~14 minutos a task atingiu o soft time limit (840s), concluiu 10 alunos e falhou no 11º. O usuário relatou que “não faz sentido” a demora.  
**Regra:** Nenhum código foi alterado; apenas análise.

---

## 1. O que aconteceu nos logs

- **Soft time limit:** 840 s (14 min)  
- **Hard time limit:** 900 s (15 min)  
- **Momento do erro:** `20:49:23` — `Soft time limit (840s) exceeded` para a task `generate_physical_forms_async[7680baeb-...]`
- **Progresso:** Itens 0 a 9 concluídos (10 alunos); no **item 10** a exceção foi lançada **dentro** de `_html_to_pdf_bytes(student_html)`, ou seja, durante a renderização WeasyPrint da **página OMR** do 11º aluno.
- Em seguida: hard limit aos 900 s e o worker foi morto com SIGKILL.

Conclusão: a task roda em um único processo; ao atingir 840 s, o Celery dispara `SoftTimeLimitExceeded` no próximo ponto “interruptível” (no caso, dentro do WeasyPrint). Por isso o 10º aluno foi concluído e o 11º falhou no meio da geração do PDF.

---

## 2. Por que “1 hora” e só 10 itens

- O **tempo que conta para o Celery** é o tempo de CPU/execução da task (até 840 s soft / 900 s hard).  
- Se você viu “1 hora” no relógio, pode incluir: fila do Celery, tempo até a task começar, ou outra execução anterior.  
- O que os limites mostram: em **14 minutos** a task conseguiu:
  - Gerar **uma vez** o PDF base (capa + questões) — WeasyPrint pesado, imagens, muitas páginas.
  - Gerar **10** PDFs “por aluno” (merge base + 1 página OMR por aluno).

Então, em termos de tempo de task:

- Parte do tempo: **1×** renderização do PDF base.  
- Restante: **10×** renderização da página OMR (uma por aluno).

Se a base levar, por exemplo, 2–4 minutos, sobram ~10–12 minutos para 10 alunos → **cerca de 1–1,2 minuto por aluno** só na etapa WeasyPrint da OMR (além de merge e disco). Isso é coerente com os ~80 s entre “Item N concluído” e “Item N+1 concluído” que você viu antes.

Ou seja: **faz sentido** que, com o limite de 840 s, a task consiga apenas ~10 alunos antes de estourar. O “não faz sentido” é em termos de **produtividade** (poucos alunos por tarefa e por minuto), não de inconsistência do fluxo.

---

## 3. Por que cada aluno demora tanto (WeasyPrint da OMR)

Cada “Item N concluído” corresponde a:

1. Montar o HTML da **página OMR** (Jinja2).  
2. Chamar WeasyPrint para esse HTML → `student_pdf_bytes`.  
3. Fazer merge (base + OMR) e gravar o PDF em disco.  
4. Chamar `update_item_done(job_id, index_0, ...)`.

O gargalo está no passo 2: **WeasyPrint**.

### 3.1 O que o WeasyPrint recebe quando gera “só OMR”

- O gerador chama o **mesmo** template `institutional_test_hybrid.html` com:
  - `include_cover=False`
  - `include_questions=False`
  - `include_answer_sheet=True`

Ou seja: **não** é um HTML mínimo “só cartão-resposta”. O template é o **mesmo** de 1479 linhas:

- **`<head>`:** todo o bloco `<style>` do arquivo é enviado (centenas de linhas de CSS), incluindo regras de capa, blocos de questões, `.subject-octagon` com `clip-path: polygon(...)` (linhas 241–278), grid, flex, etc.
- **`<body>`:** só o bloco `{% if include_answer_sheet %}` é preenchido (a div do cartão-resposta), mas o **documento** ainda é o HTML completo (doctype, head, body), com todo esse CSS.

Efeito: a cada aluno o WeasyPrint:

- Parseia o HTML inteiro e **todo** o CSS (incluindo o que não é usado na OMR).  
- Calcula layout para a **única** página que importa (a OMR), mas com um stylesheet grande e um DOM da OMR já pesado (veja abaixo).

### 3.2 Complexidade do layout da OMR (e o stack trace)

O trecho de OMR no template inclui, entre outros:

- **Cabeçalho** com vários blocos (nome da prova, aluno, estado, município, escola, turma) e uma **grade de “nome do aluno”** com **23 + 23** caixinhas (`.name-box`).
- **Instruções** com lista e exemplos de bolhas (flex).
- **Bloco do aplicador** com opções.
- **Grade de respostas:**  
  - `answer-grid-container` → `block-wrapper` → `answer-block` → para **cada questão** uma `answer-row` com:
    - `question-num` (número da questão)
    - `bubbles` com vários `.bubble` (A, B, C, D, …)

Para uma prova com dezenas de questões (ex.: 40–52), isso vira **dezenas de linhas de resposta**, cada uma com vários elementos. Ou seja: **centenas de nós no DOM** só na grade, além de cabeçalho e instruções.

O stack trace do timeout mostra WeasyPrint preso em:

- `grid_layout` (e `_resolve_tracks_sizes`)
- `flex_layout` (várias chamadas aninhadas)
- `block_level_layout` / `block_container_layout`
- `_linebox_layout` / `split_inline_box` / `max_content_width`

Isso indica que o motor de layout está trabalhando em **grid + flex** e em muitos blocos/inline. O WeasyPrint é conhecido por ser lento em documentos com muito grid/flex e muitos elementos. Ou seja: **cada página OMR é cara** por causa do tamanho do CSS e do número e da estrutura dos elementos (grid/flex da grade de respostas).

### 3.3 Resumo do custo por aluno

- **Template:** mesmo arquivo grande, com todo o CSS (incluindo clip-path, etc.).  
- **DOM da OMR:** muitas linhas de resposta (uma por questão), cada uma com grid/flex e várias bolhas.  
- **WeasyPrint:** um único processo, sem cache de layout entre alunos; a cada aluno refaz parse + layout do mesmo “tipo” de página, mas com outro nome/aluno no HTML.

Resultado: **1–2 minutos por aluno** só na etapa WeasyPrint da OMR é plausível em hardware modesto ou com muitas questões. Por isso “está demorando MUITO” em termos de experiência, mesmo que o fluxo (1 base + N OMRs) esteja correto.

---

## 4. Por que deu exatamente no item 10

- **Limites atuais** (`app/physical_tests/tasks.py`, linhas 99–100):
  - `time_limit=900`
  - `soft_time_limit=840`
- **Cálculo grosseiro:**  
  - Tempo da base: ~2–4 min.  
  - Tempo por aluno: ~1–1,5 min.  
  - 10 alunos: ~10–15 min só no loop.  
  - Total: ~12–19 min, mas a task é **cortada** em 14 min (soft) e morta em 15 min (hard).

Então é esperado que a task **passe** do soft limit por volta do 10º–11º aluno. Nos seus logs, os itens 0–9 foram concluídos e o erro ocorreu ao processar o **item 10** (11º aluno), dentro de `_html_to_pdf_bytes` para esse aluno. Ou seja: a task já estava além dos 840 s quando começou a renderizar o 11º aluno e o Celery disparou `SoftTimeLimitExceeded` durante essa renderização.

---

## 5. Conclusão (sem alterar código)

- **Por que “está demorando MUITO”:**  
  Cada aluno exige **uma** renderização WeasyPrint da página OMR. Essa página usa o template completo (HTML + CSS grande) e um DOM pesado (grade de respostas com dezenas de linhas + grid/flex). O WeasyPrint é lento nesse tipo de layout, então 1–2 min por aluno é o que o código atual produz.

- **Por que “1 hora e só 10 itens”:**  
  O limite da task é 14 min (soft) / 15 min (hard). Em 14 min você consegue aproximadamente: 1× base + 10× OMR. Por isso só 10 itens foram concluídos e o 11º falhou. Se você viu “1 hora” no relógio, pode ser tempo total (fila, outra execução, etc.); o que importa para o timeout é o tempo de execução da task (840/900 s).

- **Onde está o gargalo:**  
  Na chamada **WeasyPrint** para o HTML da OMR (`_html_to_pdf_bytes(student_html)` em `generate_institutional_test_pdf_arch4`), com:
  - Template único grande (todo o CSS do `institutional_test_hybrid.html`),
  - Página OMR com muitos elementos e uso intenso de grid/flex.

- **Por que “não faz sentido” na prática:**  
  Faz sentido que você ache inaceitável: **~1 minuto por aluno** e **só ~10 alunos por task** antes de timeout é pouco para turmas grandes. O “não faz sentido” é de **performance e limites**, não de bug no desenho do fluxo (1 base + N OMRs).

Em um próximo passo (quando quiser alterar código), as direções úteis seriam: **aumentar** `time_limit`/`soft_time_limit` para turmas grandes; **reduzir** o custo por aluno (template/CSS mínimos só para OMR, simplificar grid/flex da grade, ou trocar abordagem de geração da OMR); e/ou **dividir** o trabalho (ex.: mais de uma task por prova, cada uma com um subconjunto de alunos), sempre respeitando os limites do Celery e do worker.
