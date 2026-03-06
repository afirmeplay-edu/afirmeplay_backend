# Exemplo de retorno: GET /answer-sheets/resultados-agregados

**Query params:** `estado=SP&municipio=<city_id>&gabarito=<gabarito_id>&escola=<school_id>`

(Estado e município obrigatórios; gabarito, escola, série e turma opcionais para refinar o escopo.)

---

## Exemplo de resposta (200 OK)

```json
{
  "nivel_granularidade": "escola",
  "filtros_aplicados": {
    "estado": "SP",
    "municipio": "uuid-municipio-xyz",
    "escola": "uuid-escola-abc",
    "serie": "all",
    "turma": "all",
    "gabarito": "uuid-gabarito-123"
  },
  "estatisticas_gerais": {
    "tipo": "escola",
    "nome": "Escola Municipal Exemplo",
    "estado": "SP",
    "municipio": "São Paulo",
    "escola": "Escola Municipal Exemplo",
    "serie": null,
    "total_escolas": 1,
    "total_series": 2,
    "total_turmas": 4,
    "total_gabaritos": 1,
    "total_alunos": 120,
    "alunos_participantes": 115,
    "alunos_pendentes": 5,
    "alunos_ausentes": 0,
    "media_nota_geral": 7.45,
    "media_proficiencia_geral": 68.2,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 8,
      "basico": 35,
      "adequado": 52,
      "avancado": 20
    }
  },
  "resultados_detalhados": {
    "gabaritos": [
      {
        "id": "serie_uuid-grade-1",
        "titulo": "Avaliação 5º Ano - 5º Ano",
        "serie": "5º Ano",
        "turma": "Todas as turmas",
        "escola": "Escola Municipal Exemplo",
        "municipio": "São Paulo",
        "estado": "SP",
        "total_alunos": 60,
        "alunos_participantes": 58,
        "alunos_pendentes": 2,
        "media_nota": 7.8,
        "media_proficiencia": 72.5,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 2,
          "basico": 15,
          "adequado": 28,
          "avancado": 13
        }
      },
      {
        "id": "serie_uuid-grade-2",
        "titulo": "Avaliação 5º Ano - 4º Ano",
        "serie": "4º Ano",
        "turma": "Todas as turmas",
        "escola": "Escola Municipal Exemplo",
        "municipio": "São Paulo",
        "estado": "SP",
        "total_alunos": 60,
        "alunos_participantes": 57,
        "alunos_pendentes": 3,
        "media_nota": 7.1,
        "media_proficiencia": 63.9,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 6,
          "basico": 20,
          "adequado": 24,
          "avancado": 7
        }
      }
    ],
    "paginacao": {
      "page": 1,
      "per_page": 2,
      "total": 2,
      "total_pages": 1
    }
  },
  "tabela_detalhada": {
    "alunos": [
      {
        "student_id": "uuid-aluno-1",
        "nome": "Maria Silva",
        "turma": "5º A",
        "serie": "5º Ano",
        "grade": 8.5,
        "proficiency": 78.0,
        "classification": "Adequado",
        "score_percentage": 85.0,
        "correct_answers": 17,
        "total_questions": 20
      },
      {
        "student_id": "uuid-aluno-2",
        "nome": "João Santos",
        "turma": "5º A",
        "serie": "5º Ano",
        "grade": 6.0,
        "proficiency": 55.0,
        "classification": "Básico",
        "score_percentage": 60.0,
        "correct_answers": 12,
        "total_questions": 20
      }
    ]
  },
  "ranking": [
    {
      "posicao": 1,
      "student_id": "uuid-aluno-1",
      "nome": "Maria Silva",
      "grade": 8.5,
      "proficiency": 78.0,
      "classification": "Adequado",
      "score_percentage": 85.0
    },
    {
      "posicao": 2,
      "student_id": "uuid-aluno-2",
      "nome": "João Santos",
      "grade": 6.0,
      "proficiency": 55.0,
      "classification": "Básico",
      "score_percentage": 60.0
    }
  ],
  "opcoes_proximos_filtros": {
    "gabaritos": [
      { "id": "uuid-gabarito-123", "titulo": "Avaliação 5º Ano" }
    ],
    "escolas": [
      { "id": "uuid-escola-abc", "name": "Escola Municipal Exemplo" }
    ],
    "series": [
      { "id": "uuid-grade-1", "name": "5º Ano" },
      { "id": "uuid-grade-2", "name": "4º Ano" }
    ],
    "turmas": [
      { "id": "uuid-turma-1", "name": "5º A" },
      { "id": "uuid-turma-2", "name": "5º B" },
      { "id": "uuid-turma-3", "name": "4º A" },
      { "id": "uuid-turma-4", "name": "4º B" }
    ]
  }
}
```

---

- **nivel_granularidade:** `municipio` | `escola` | `serie` | `turma`, conforme os filtros.
- **estatisticas_gerais:** totais do escopo (alunos, participantes, média, distribuição por classificação).
- **resultados_detalhados.gabaritos:** lista agregada por escola, série ou turma (conforme o nível).
- **tabela_detalhada.alunos:** um registro por aluno do escopo com resultado no gabarito.
- **ranking:** alunos ordenados por nota (e proficiência) no gabarito.
- **opcoes_proximos_filtros:** opções para os próximos níveis (gabaritos, escolas, séries, turmas).
