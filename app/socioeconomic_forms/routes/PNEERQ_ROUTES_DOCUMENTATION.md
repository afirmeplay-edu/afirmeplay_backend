# Documentação das Rotas PNEERQ (Equidade Racial) — Formulários Socioeconômicos

## Visão Geral

As rotas PNEERQ retornam indicadores de equidade racial calculados **a partir das respostas dos formulários socioeconômicos** (`aluno-jovem` e `aluno-velho`).

**Base URLs:**
- Por formulário: `/forms`
- Agregado (escopo): `/forms/aggregated`

**Autenticação:** JWT no header `Authorization: Bearer <token>`

**Permissões (por formulário):** `admin`, `tecadm`, `diretor`, `coordenador`  
**Permissões (agregado):** requer JWT (mesmo padrão das rotas agregadas existentes)

**Filtros hierárquicos (query params):**
- `state`: UF (ex.: `AL`, `SP`)
- `municipio`: UUID do município
- `escola`: ID da escola
- `serie`: UUID da série
- `turma`: UUID da turma

> Observação: a hierarquia é a mesma do módulo (`state → municipio → escola → serie → turma`).

---

## 1) Por formulário — GET `/forms/<formId>/results/pneerq`

### Descrição
Retorna o relatório PNEERQ calculado para **um formulário específico**.

### Endpoint
```
GET /forms/<formId>/results/pneerq
```

### Query Parameters (opcionais)
- `state` (string)
- `municipio` (string UUID)
- `escola` (string)
- `serie` (string UUID)
- `turma` (string UUID)
- `ageDistortionDelta` (**DEPRECADO**): se enviado, será ignorado (a regra de distorção vem do template: `q1` + `q2`).

### Comportamento (cache + background)
- Se o cache estiver pronto: retorna **200** com o resultado.
- Se o cache não existir ou estiver dirty: retorna **202** com `status=processing` e o frontend deve fazer **polling na mesma URL** até receber **200**.

### Response (202 Accepted)
```json
{
  "status": "processing",
  "message": "Relatório PNEERQ sendo gerado em background. Faça polling neste mesmo endpoint (GET pneerq) até receber 200 com os dados.",
  "pollSameUrl": true,
  "cacheStatus": {
    "status": "not_found",
    "has_result": false,
    "is_dirty": true,
    "student_count": 0,
    "last_update": null
  }
}
```

### Response (200 OK) — Shape (alto nível)
```json
{
  "formId": "uuid",
  "totalRespostas": 123,
  "filtros": { "...": "..." },
  "gruposRaciais": {
    "disponiveis": ["Branca", "PretaParda", "Outras", "NaoDeclarada", "NaoInformada"],
    "definicao": { "...": ["..."] }
  },
  "metadados": {
    "ageDistortionRule": "template_thresholds",
    "ageDistortionThresholds": { "1º Ano": 8, "2º Ano": 9, "...": 16 },
    "fonte": "forms"
  },
  "eixos": {
    "eixo2_diagnostico_monitoramento": {
      "nome": "Eixo 2 — Diagnóstico e Monitoramento",
      "indicadores": [
        {
          "id": "age_grade_distortion",
          "nome": "Distorção Idade-Série (estimada)",
          "descricao": " ... ",
          "unidade": "percent",
          "metricas": { "numerador": 10, "denominador": 100, "valor": 10.0 },
          "porGrupoRacial": {
            "Branca": { "numerador": 2, "denominador": 40, "valor": 5.0 },
            "PretaParda": { "numerador": 8, "denominador": 60, "valor": 13.33 }
          }
        }
      ]
    }
  }
}
```

---

## 2) Agregado por escopo — GET `/forms/aggregated/results/pneerq`

### Descrição
Retorna o PNEERQ consolidado de **todos os formulários aplicados** dentro do escopo.

### Endpoint
```
GET /forms/aggregated/results/pneerq
```

### Query Parameters (opcionais)
- `state` (string)
- `municipio` (string UUID)
- `escola` (string)
- `serie` (string UUID)
- `turma` (string UUID)
- `ageDistortionDelta` (**DEPRECADO**) — ignorado.

### Response (200 OK) — Shape (alto nível)
```json
{
  "escopo": { "...": "..." },
  "formularios": [
    { "formId": "uuid", "formTitle": "titulo", "formType": "aluno-jovem", "totalRespostas": 120 }
  ],
  "totalFormularios": 3,
  "totalRespostas": 456,
  "pneerqConsolidado": {
    "gruposRaciais": { "...": "..." },
    "metadados": { "...": "..." },
    "eixos": { "...": "..." }
  },
  "geradoEm": "ISO-8601"
}
```

---

## Resumo das Rotas

| Rota | Método | Descrição |
|------|--------|-----------|
| `/forms/<formId>/results/pneerq` | GET | PNEERQ por formulário (cache + 202 + polling na mesma URL) |
| `/forms/aggregated/results/pneerq` | GET | PNEERQ agregado por escopo |

