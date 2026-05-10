# Guia de Integração Frontend — PNEERQ (Equidade Racial)

Este guia descreve como consumir, no frontend, os indicadores PNEERQ calculados **a partir das respostas dos formulários socioeconômicos** (`aluno-jovem` / `aluno-velho`).

## Endpoints

### 1) Por formulário (cache + background)

**GET** `/forms/{formId}/results/pneerq`

**Query params (mesmos filtros hierárquicos):**
- `state` (string)
- `municipio` (UUID)
- `escola` (string/UUID)
- `serie` (UUID)
- `turma` (UUID)
- `ageDistortionDelta` (**deprecado**): se enviado, será ignorado (a regra vem do template: `q1` + `q2`).

**Comportamento:**
- Se o cache estiver pronto: retorna **200** com o JSON completo.
- Se o cache não existir / estiver dirty: retorna **202** com `status=processing`.
  - O frontend deve fazer **polling na mesma URL** até receber **200**.

### 2) Agregado por escopo (todos os formulários do escopo)

**GET** `/forms/aggregated/results/pneerq`

**Query params:** os mesmos acima (`state/municipio/escola/serie/turma`).

**Comportamento:**
- Retorna **200** imediatamente (consolida resultados por formulário, reaproveitando o cache PNEERQ por formulário quando existir).

## Shape do JSON (alto nível)

### Por formulário (`/forms/{id}/results/pneerq`)

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
    "ageDistortionThresholds": { "1º Ano": 8, "...": 16 },
    "fonte": "forms"
  },
  "eixos": {
    "eixo2_diagnostico_monitoramento": {
      "nome": "Eixo 2 — Diagnóstico e Monitoramento",
      "indicadores": [
        {
          "id": "age_grade_distortion",
          "nome": "...",
          "descricao": "...",
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

### Agregado (`/forms/aggregated/results/pneerq`)

```json
{
  "escopo": { "...": "..." },
  "formularios": [{ "formId": "...", "formTitle": "...", "totalRespostas": 123 }],
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

## Indicadores (regras)

### Eixo 2 — Diagnóstico e Monitoramento
- **`age_grade_distortion`**: % em distorção idade-série conforme a tabela do template (base: série/curso + idade).
- **`dropout_history`**: % `q21 != "Nunca"`

### Eixo 3/4 — Formação e Currículo
- **`curricular_silencing_index`**: % `q23d` em `["Poucos deles", "Nenhum deles"]`

### Eixo 5 — Clima/Segurança
- **`violence_bullying_low_approach`**: % `q23f` em `["Poucos deles", "Nenhum deles"]`
- **`safety_perception_low`**: % `q24d` em `["Discordo", "Discordo totalmente"]`

### Eixo 6 — Afirmação de trajetórias
- **`teacher_expectation_low_capable`**: % `q24h` em `["Discordo", "Discordo totalmente"]`
- **`teacher_expectation_low_motivation`**: % `q24i` em `["Discordo", "Discordo totalmente"]`

### Eixo 7 — Difusão de saberes
- **`home_language_non_portuguese`**: % `q4 != "Português"`

## Polling (padrão do módulo)

Para `/forms/{id}/results/pneerq`:
- Se receber `202` com `pollSameUrl=true`, repetir **GET na mesma URL** com os mesmos filtros até receber `200`.

