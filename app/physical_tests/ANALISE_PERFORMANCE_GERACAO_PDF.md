# Análise de performance: por que a geração está demorando mais de 1 hora (22 alunos, 52 questões)

**Contexto:** Geração com configurações atuais não conclui em tempo aceitável (>1h). Este documento analisa as causas **sem alterar código**.

---

## 1. A nova arquitetura (base + OMR + merge) vai diminuir o tempo?

**Sim.** Ela reduz o trabalho do WeasyPrint e do pipeline como um todo:

- **Hoje (Architecture 4):** 1× PDF de questões + **22× PDF (capa + OMR)** = 22 documentos de 2 páginas cada.
- **Proposta:** 1× PDF base (capa + questões) + **22× PDF só OMR** = 22 documentos de **1 página** cada.

Menos páginas por aluno implica menos renderização, menos uso de fonte e menos I/O por documento. Além disso, **hoje existe um custo extra que não tem relação com a arquitetura e que sozinho já explica boa parte da lentidão**: o sistema está fazendo **trabalho desperdiçado** por aluno (ver abaixo). Corrigir esse desperdício tende a dar ganho imediato; a arquitetura base+OMR dá ganho adicional.

---

## 2. Causa crítica: trabalho desperdiçado por aluno (22×)

No fluxo **Architecture 4** (`generate_institutional_test_pdf_arch4`), **para cada um dos 22 alunos** o código chama:

```text
answer_sheet_image = self._generate_answer_sheet_base64(student, questions_data, test_data)
```

Essa função:

1. Abre um arquivo temporário em disco.
2. Chama `gerar_formulario_com_qrcode()` do **formularios.py** (PIL/Image), que:
   - Carrega várias fontes (Arial/DejaVu — correspondem aos logs "Tentando fonte UTF-8: arial.ttf").
   - Cria uma imagem PIL do formulário completo (cabeçalho, grid de 52 questões, QR, bordas — daí os logs "Borda grossa da tabela removida" / "Borda grossa adicionada ao formulario").
   - Salva a imagem no arquivo temporário (I/O em disco).
3. Lê o arquivo, converte para base64 e retorna.
4. O valor é passado ao template como `answer_sheet_image`.

Porém, no template **institutional_test_hybrid.html** a variável **`answer_sheet_image` não é usada**. O cartão-resposta (OMR) é desenhado inteiramente pelo HTML/CSS da div `.answer-sheet` (WeasyPrint). Ou seja:

- **22 vezes** o sistema gera um formulário completo via PIL (fontes, desenho, arquivo, base64).
- **22 vezes** esse resultado é ignorado pelo template.

Conclusão: esse custo é **100% desperdiçado** e provavelmente é uma das principais causas da demora (vários minutos só nessa parte, dependendo do ambiente). Os logs que você viu (fontes Arial, “Borda grossa”, etc.) batem com esse caminho de código.

---

## 3. Outros gargalos (resumo)

| Gargalo | Onde | Impacto |
|--------|------|--------|
| **22× `_generate_answer_sheet_base64`** (acima) | `institutional_test_weasyprint_generator.py` (arch4), por aluno | **Alto** – trabalho totalmente desperdiçado. |
| **1× WeasyPrint “questões”** | Um único HTML com 52 questões; imagens em base64 (MinIO) | **Alto** – documento grande, muitas imagens, uma única renderização pesada. |
| **22× WeasyPrint “capa + OMR”** | Dois páginas por aluno (capa + cartão) | **Médio** – cada documento carrega CSS, fontes (subsetting nos logs) e renderiza 2 páginas. |
| **Carregamento de fontes (WeasyPrint)** | Cada documento WeasyPrint (1 + 22 = 23) | **Médio** – logs de “Glyph IDs”, “subsetted”, etc. repetidos por documento. |
| **Processamento sequencial** | Loop único por aluno | **Médio** – não há paralelismo; tempo total = soma dos tempos por aluno. |
| **Imagens das questões** | Download MinIO + inline base64 na etapa de questões | **Variável** – feito uma vez; o custo está na rede e no tamanho do HTML/PDF de questões. |

Ou seja: além do desperdício das 22 gerações de formulário, o tempo é composto por (1) um PDF de questões pesado e (2) 22 PDFs de capa+OMR, cada um com seu custo de fontes e renderização.

---

## 4. Por que mais de 1 hora?

Com 22 alunos e 52 questões (e algumas imagens), uma estimativa grosseira:

- **Desperdício:** 22× `gerar_formulario_com_qrcode` (PIL + fontes + I/O). Se cada chamada levar ~1–2 min em ambiente limitado (CPU/memória), já são **~22–44 minutos** só nisso.
- **WeasyPrint questões:** 1× documento grande (52 questões + imagens). Pode levar **5–15+ minutos** dependendo de tamanho das imagens e do hardware.
- **WeasyPrint por aluno:** 22× (capa + OMR). Se cada um levar 1–3 min, são **~22–66 minutos**.

Somando, é plausível ultrapassar **1 hora** mesmo com apenas 22 alunos, principalmente por causa do trabalho desperdiçado e do custo do WeasyPrint por documento.

---

## 5. O que tende a ajudar (ordem de prioridade)

1. **Remover a chamada a `_generate_answer_sheet_base64` no fluxo arch4** (ou não preencher `answer_sheet_image` quando o template não a usar).  
   - Elimina 22 gerações completas de formulário (PIL, fontes, I/O).  
   - **Nenhuma mudança no layout do OMR** – o cartão continua sendo o HTML/CSS do template.

2. **Implementar a arquitetura “base + só OMR por aluno + merge”.**  
   - Reduz o trabalho do WeasyPrint por aluno (1 página em vez de 2).  
   - Menos páginas e documentos menores → menos tempo de render e de fontes.

3. **Otimizações adicionais (para depois):**  
   - Cache de fontes / reuso de documento WeasyPrint quando possível.  
   - Reduzir resolução/tamanho das imagens das questões antes de colar em base64.  
   - Paralelizar a geração por aluno (vários workers ou processos) se o Celery e o servidor permitirem.

---

## 6. Resposta direta às suas perguntas

- **“Isso vai diminuir o tempo de geração?”**  
  **Sim.** A arquitetura base + OMR + merge reduz o trabalho por aluno. E o maior ganho imediato vem de **deixar de chamar `_generate_answer_sheet_base64`** no arch4, pois hoje esse custo é puro desperdício.

- **“Está demorando muito, mais de 1h e ainda não gerou”**  
  A análise indica que isso é explicado por: (1) 22 gerações completas de formulário (PIL) que não são usadas; (2) um PDF de questões pesado (52 questões + imagens); (3) 22 PDFs capa+OMR com WeasyPrint. Tudo sequencial.

- **“Isso NÃO PODE ACONTECER”**  
  Para evitar isso, as mudanças prioritárias são: eliminar o trabalho desperdiçado (22× `_generate_answer_sheet_base64`) e, em seguida, adotar a arquitetura base + apenas OMR por aluno + merge, sem alterar o layout do OMR.

**Nenhum código foi alterado nesta análise;** apenas identificação das causas e das medidas que tendem a reduzir o tempo de geração.
