# Contrato: gabarito multi-série (cartão-resposta)

## Regras

1. **Nunca** usar `title` para inferir série/curso (escala de nota/proficiência).
2. O gabarito guarda as séries aplicáveis em `grades`: `[{"id": "<uuid>", "name": "9º Ano"}, ...]`.
3. Correção do aluno usa a **série do aluno** (`grade_id_snapshot` / turma).
4. Relatório com `?serie=<grade_id>` agrega na escala dessa série.
5. Relatório **sem** `serie` em gabarito multi-série: `por_serie[]` + `requer_filtro_serie: true` (não mistura Anos Iniciais × Finais).

---

## 1) Criar gabarito — `POST /answer-sheets/create-gabaritos`

```json
{
  "title": "2º AVALIA CHÃ PRETA",
  "num_questions": 52,
  "correct_answers": { "1": "A", "2": "B" },
  "use_blocks": true,
  "blocks_config": {},
  "grade_ids": [
    "uuid-2-ano",
    "uuid-4-ano",
    "uuid-5-ano",
    "uuid-8-ano"
  ]
}
```

Alternativa:

```json
{
  "grades": [
    { "id": "uuid-5-ano", "name": "5º Ano" },
    { "id": "uuid-8-ano", "name": "8º Ano" }
  ]
}
```

**Resposta 201 (trecho):**

```json
{
  "gabarito_id": "d301abce-...",
  "title": "2º AVALIA CHÃ PRETA",
  "num_questions": 52,
  "grades": [
    { "id": "uuid-5-ano", "name": "5º Ano" },
    { "id": "uuid-8-ano", "name": "8º Ano" }
  ],
  "grade_id": null,
  "grade_name": null
}
```

> Com **1** série, `grade_id` / `grade_name` são preenchidos (atalho legado). Com **N**, ficam `null` e a fonte da verdade é `grades`.

---

## 2) Gerar PDFs — `POST /answer-sheets/generate`

```json
{
  "gabarito_id": "d301abce-...",
  "grade_ids": ["uuid-5-ano", "uuid-8-ano"],
  "school_ids": []
}
```

As séries do body (ou das turmas geradas) são **persistidas** no gabarito.

---

## 3) Resultados agregados — uma série

`GET /answer-sheets/resultados-agregados?estado=ALAGOAS&municipio=<city_id>&gabarito=<id>&serie=<grade_id_5_ano>`

```json
{
  "nivel_granularidade": "serie",
  "filtros_aplicados": {
    "estado": "ALAGOAS",
    "municipio": "0b92b11b-...",
    "escola": null,
    "serie": "uuid-5-ano",
    "turma": null,
    "gabarito": "d301abce-...",
    "periodo": null
  },
  "series_do_gabarito": [
    { "id": "uuid-5-ano", "name": "5º Ano" },
    { "id": "uuid-8-ano", "name": "8º Ano" }
  ],
  "requer_filtro_serie": false,
  "por_serie": [],
  "estatisticas_gerais": {
    "serie": "5º Ano",
    "media_nota_geral": 6.04,
    "media_proficiencia_geral": 216.09,
    "por_disciplina": [
      {
        "disciplina": "Português",
        "media_nota": 6.04,
        "media_proficiencia": 216.09
      },
      {
        "disciplina": "Matemática",
        "media_nota": 6.28,
        "media_proficiencia": 228.47
      }
    ]
  },
  "resultados_por_disciplina": [],
  "resultados_detalhados": { "gabaritos": [], "paginacao": {} },
  "tabela_detalhada": { "disciplinas": [], "geral": { "alunos": [] } },
  "ranking": [],
  "opcoes_proximos_filtros": {}
}
```

Escalas: 5º → **Anos Iniciais**; 8º → **Anos Finais**.

---

## 4) Resultados agregados — multi-série sem filtro

`GET /answer-sheets/resultados-agregados?estado=ALAGOAS&municipio=<city_id>&gabarito=<id>`

```json
{
  "nivel_granularidade": "municipio",
  "filtros_aplicados": {
    "estado": "ALAGOAS",
    "municipio": "0b92b11b-...",
    "escola": null,
    "serie": null,
    "turma": null,
    "gabarito": "d301abce-...",
    "periodo": null
  },
  "series_do_gabarito": [
    { "id": "uuid-5-ano", "name": "5º Ano" },
    { "id": "uuid-8-ano", "name": "8º Ano" }
  ],
  "requer_filtro_serie": true,
  "estatisticas_gerais": {
    "total_alunos": 200,
    "alunos_participantes": 180,
    "percentual_comparecimento": 90.0,
    "media_nota_geral": null,
    "media_proficiencia_geral": null,
    "nivel_classificacao": null,
    "requer_filtro_serie": true,
    "por_disciplina": []
  },
  "resultados_por_disciplina": [],
  "por_serie": [
    {
      "serie_id": "uuid-5-ano",
      "serie": "5º Ano",
      "course_name": "Anos Iniciais",
      "estatisticas_gerais": {
        "serie": "5º Ano",
        "media_nota_geral": 6.1,
        "media_proficiencia_geral": 220.0,
        "por_disciplina": []
      },
      "resultados_por_disciplina": []
    },
    {
      "serie_id": "uuid-8-ano",
      "serie": "8º Ano",
      "course_name": "Anos Finais",
      "estatisticas_gerais": {
        "serie": "8º Ano",
        "media_nota_geral": 4.2,
        "media_proficiencia_geral": 225.0,
        "por_disciplina": []
      },
      "resultados_por_disciplina": []
    }
  ],
  "resultados_detalhados": { "gabaritos": [], "paginacao": {} },
  "tabela_detalhada": { "disciplinas": [], "geral": { "alunos": [] } },
  "ranking": [],
  "opcoes_proximos_filtros": {}
}
```

### Como o front deve consumir

| Situação | O que usar |
|----------|------------|
| Usuário escolheu série | `estatisticas_gerais` + `resultados_por_disciplina` (topo) |
| Multi-série sem série | `por_serie[]` (um card/bloco por série); ignore `media_nota_geral` do topo |
| Listagem de gabaritos | campo `grades` |

---

## Migração

Rodar (DEV/PROD, com `DATABASE_URL` apontando para o banco):

```bash
python migrations_multitenant/0006_add_grades_json_to_answer_sheet_gabaritos.py
```

Faz `ADD COLUMN grades` em cada `city_*` e backfill a partir de `grade_id` ou `grade_id_snapshot` dos resultados.
