# Exemplo de Resposta da Rota de Avaliações

## Rota
```
GET /evaluation-results/avaliacoes?estado=São Paulo&municipio=Campo Alegre&avaliacao=all&escola=all&serie=all&turma=all
```

## Exemplo de Resposta - Estado + Município + Avaliação "all"

```json
{
  "nivel_granularidade": "municipio",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "Campo Alegre",
    "escola": "all",
    "serie": "all",
    "turma": "all",
    "avaliacao": "all"
  },
  "estatisticas_gerais": {
    "tipo": "municipio",
    "nome": "Campo Alegre",
    "estado": "São Paulo",
    "municipio": "Campo Alegre",
    "escola": null,
    "serie": null,
    "total_escolas": 5,
    "total_series": 12,
    "total_turmas": 45,
    "total_avaliacoes": 8,
    "total_alunos": 1250,
    "alunos_participantes": 1180,
    "alunos_pendentes": 0,
    "alunos_ausentes": 70,
    "media_nota_geral": 7.2,
    "media_proficiencia_geral": 645.5,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 45,
      "basico": 320,
      "adequado": 580,
      "avancado": 235
    }
  },
  "resultados_por_disciplina": [
    {
      "disciplina": "Matemática",
      "total_avaliacoes": 3,
      "total_alunos": 1250,
      "alunos_participantes": 1180,
      "alunos_pendentes": 0,
      "alunos_ausentes": 70,
      "media_nota": 6.8,
      "media_proficiencia": 620.3,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 65,
        "basico": 380,
        "adequado": 520,
        "avancado": 215
      }
    },
    {
      "disciplina": "Português",
      "total_avaliacoes": 3,
      "total_alunos": 1250,
      "alunos_participantes": 1180,
      "alunos_pendentes": 0,
      "alunos_ausentes": 70,
      "media_nota": 7.5,
      "media_proficiencia": 670.2,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 25,
        "basico": 260,
        "adequado": 640,
        "avancado": 255
      }
    }
  ],
  "resultados_detalhados": {
    "avaliacoes": [
      {
        "id": "test-001",
        "titulo": "Avaliação de Matemática - 9º Ano",
        "disciplina": "Matemática",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "turma": "9º A",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "Campo Alegre",
        "estado": "São Paulo",
        "data_aplicacao": "2024-01-15T10:00:00Z",
        "status": "concluida",
        "total_alunos": 1250,
        "alunos_participantes": 1180,
        "alunos_pendentes": 0,
        "alunos_ausentes": 70,
        "media_nota": 7.2,
        "media_proficiencia": 645.5,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 45,
          "basico": 320,
          "adequado": 580,
          "avancado": 235
        }
      },
      {
        "id": "test-002",
        "titulo": "Avaliação de Português - 9º Ano",
        "disciplina": "Português",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "turma": "9º A",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "Campo Alegre",
        "estado": "São Paulo",
        "data_aplicacao": "2024-01-16T10:00:00Z",
        "status": "concluida",
        "total_alunos": 1250,
        "alunos_participantes": 1180,
        "alunos_pendentes": 0,
        "alunos_ausentes": 70,
        "media_nota": 7.2,
        "media_proficiencia": 645.5,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 45,
          "basico": 320,
          "adequado": 580,
          "avancado": 235
        }
      }
    ],
    "paginacao": {
      "page": 1,
      "per_page": 10,
      "total": 8,
      "total_pages": 1
    }
  },
  "opcoes_proximos_filtros": {
    "avaliacoes": [
      {"id": "test-001", "titulo": "Avaliação de Matemática - 9º Ano"},
      {"id": "test-002", "titulo": "Avaliação de Português - 9º Ano"}
    ],
    "escolas": [
      {"id": "school-001", "name": "Escola Municipal Campo Alegre"},
      {"id": "school-002", "name": "Escola Estadual João Silva"}
    ],
    "series": [],
    "turmas": []
  }
}
```

## Exemplo de Resposta - Estado + Município + Avaliação + Escola "all"

```json
{
  "nivel_granularidade": "escola",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "Campo Alegre",
    "escola": "school-001",
    "serie": "all",
    "turma": "all",
    "avaliacao": "test-001"
  },
  "estatisticas_gerais": {
    "tipo": "escola",
    "nome": "Escola Municipal Campo Alegre",
    "estado": "São Paulo",
    "municipio": "Campo Alegre",
    "escola": "Escola Municipal Campo Alegre",
    "serie": null,
    "total_escolas": 1,
    "total_series": 8,
    "total_turmas": 32,
    "total_avaliacoes": 1,
    "total_alunos": 450,
    "alunos_participantes": 425,
    "alunos_pendentes": 0,
    "alunos_ausentes": 25,
    "media_nota_geral": 7.8,
    "media_proficiencia_geral": 680.2,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 15,
      "basico": 120,
      "adequado": 200,
      "avancado": 90
    }
  },
  "resultados_detalhados": {
    "avaliacoes": [
      {
        "id": "test-001",
        "titulo": "Avaliação de Matemática - 9º Ano",
        "disciplina": "Matemática",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "turma": "9º A",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "Campo Alegre",
        "estado": "São Paulo",
        "data_aplicacao": "2024-01-15T10:00:00Z",
        "status": "concluida",
        "total_alunos": 450,
        "alunos_participantes": 425,
        "alunos_pendentes": 0,
        "alunos_ausentes": 25,
        "media_nota": 7.8,
        "media_proficiencia": 680.2,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 15,
          "basico": 120,
          "adequado": 200,
          "avancado": 90
        }
      }
    ],
    "paginacao": {
      "page": 1,
      "per_page": 10,
      "total": 1,
      "total_pages": 1
    }
  },
  "opcoes_proximos_filtros": {
    "avaliacoes": [],
    "escolas": [],
    "series": [
      {"id": "grade-001", "name": "9º Ano"},
      {"id": "grade-002", "name": "8º Ano"}
    ],
    "turmas": []
  }
}
```

## Parâmetros da Rota

### Query Parameters:
- `estado` (obrigatório): Estado geográfico (não pode ser 'all')
- `municipio` (obrigatório): Município do estado
- `avaliacao` (opcional): ID da avaliação específica ou 'all' para todas as avaliações
- `escola` (opcional): ID da escola ou 'all' para todas as escolas
- `serie` (opcional): ID da série ou 'all' para todas as séries
- `turma` (opcional): ID da turma ou 'all' para todas as turmas
- `page` (opcional): Número da página (padrão: 1)
- `per_page` (opcional): Itens por página (padrão: 10, máximo: 100)

### Exemplos de URLs:

1. **Estado + Município + Avaliação "all":**
   ```
   GET /evaluation-results/avaliacoes?estado=São Paulo&municipio=Campo Alegre&avaliacao=all
   ```

2. **Estado + Município + Avaliação + Escola "all":**
   ```
   GET /evaluation-results/avaliacoes?estado=São Paulo&municipio=Campo Alegre&avaliacao=test-001&escola=all
   ```

3. **Estado + Município + Avaliação + Escola + Série "all":**
   ```
   GET /evaluation-results/avaliacoes?estado=São Paulo&municipio=Campo Alegre&avaliacao=test-001&escola=school-001&serie=all
   ```

4. **Estado + Município + Avaliação + Escola + Série + Turma "all":**
   ```
   GET /evaluation-results/avaliacoes?estado=São Paulo&municipio=Campo Alegre&avaliacao=test-001&escola=school-001&serie=grade-001&turma=all
   ```

## Observações Importantes

1. **Estatísticas Consolidadas:** Todos os resultados mostram estatísticas consolidadas do escopo selecionado, não individuais por avaliação.

2. **Hierarquia de Filtros:** Os filtros seguem a hierarquia: Estado → Município → Avaliação → Escola → Série → Turma.

3. **Valor "all":** Quando um filtro tem valor "all", retorna dados de todos os registros daquele nível dentro do contexto dos filtros anteriores.

4. **Cálculos Corretos:** 
   - **Município:** Calcula estatísticas de todas as escolas do município
   - **Escola:** Calcula estatísticas de todas as séries da escola
   - **Série:** Calcula estatísticas de todas as turmas da série
   - **Turma:** Calcula estatísticas da turma específica
