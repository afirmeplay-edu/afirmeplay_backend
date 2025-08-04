# Nova Rota de Avaliações - Formato Detalhado

## Endpoint
```
GET /evaluation-results/avaliacoes
```

## Autenticação
Requer JWT token válido com roles: `admin`, `professor`, `coordenador`, `diretor`

## Parâmetros de Query
- `estado` (opcional): Nome ou ID do estado
- `municipio` (opcional): Nome ou ID do município
- `escola` (opcional): Nome ou ID da escola
- `serie` (opcional): Nome ou ID da série/grade
- `turma` (opcional): Nome ou ID da turma
- `avaliacao` (opcional): Nome ou ID da avaliação
- `page` (opcional): Número da página (padrão: 1)
- `per_page` (opcional): Itens por página (padrão: 10, máximo: 100)

**Nota**: É necessário aplicar pelo menos 2 filtros.

## Exemplo de Uso

### 1. Buscar avaliações por estado e município
```
GET /evaluation-results/avaliacoes?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c
```

### 2. Buscar avaliações por escola e série
```
GET /evaluation-results/avaliacoes?escola=123e4567-e89b-12d3-a456-426614174000&serie=456e7890-f12g-34h5-i678-901234567890
```

### 3. Buscar avaliações com todos os filtros
```
GET /evaluation-results/avaliacoes?estado=ALAGOAS&municipio=618f56d1-2167-439e-bf0b-d3d2be54271c&escola=123e4567-e89b-12d3-a456-426614174000&serie=456e7890-f12g-34h5-i678-901234567890&turma=abc123-def456-ghi789&avaliacao=test-123e4567-e89b-12d3-a456-426614174000
```

## Formato de Resposta

```json
{
  "nivel_granularidade": "escola",
  "filtros_aplicados": {
    "estado": "ALAGOAS",
    "municipio": "618f56d1-2167-439e-bf0b-d3d2be54271c",
    "escola": "123e4567-e89b-12d3-a456-426614174000",
    "serie": "456e7890-f12g-34h5-i678-901234567890",
    "turma": "abc123-def456-ghi789",
    "avaliacao": "test-123e4567-e89b-12d3-a456-426614174000"
  },
  "estatisticas_gerais": {
    "tipo": "escola",
    "nome": "Escola Municipal Campo Alegre",
    "estado": "ALAGOAS",
    "municipio": "SÃO MIGUEL DOS CAMPOS",
    "escola": "Escola Municipal Campo Alegre",
    "serie": "9º Ano",
    "total_escolas": 1,
    "total_series": 2,
    "total_turmas": 3,
    "total_avaliacoes": 2,
    "total_alunos": 60,
    "alunos_participantes": 55,
    "alunos_pendentes": 3,
    "alunos_ausentes": 2,
    "media_nota_geral": 7.5,
    "media_proficiencia_geral": 250.2,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 5,
      "basico": 15,
      "adequado": 25,
      "avancado": 10
    }
  },
  "resultados_por_disciplina": [
    {
      "disciplina": "Matemática",
      "total_avaliacoes": 1,
      "total_alunos": 30,
      "alunos_participantes": 28,
      "alunos_pendentes": 1,
      "alunos_ausentes": 1,
      "media_nota": 7.8,
      "media_proficiencia": 255.0,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 2,
        "basico": 7,
        "adequado": 13,
        "avancado": 6
      }
    },
    {
      "disciplina": "Português",
      "total_avaliacoes": 1,
      "total_alunos": 30,
      "alunos_participantes": 27,
      "alunos_pendentes": 2,
      "alunos_ausentes": 1,
      "media_nota": 7.2,
      "media_proficiencia": 245.4,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 3,
        "basico": 8,
        "adequado": 12,
        "avancado": 4
      }
    }
  ],
  "resultados_detalhados": {
    "avaliacoes": [
      {
        "id": "test-123e4567-e89b-12d3-a456-426614174000",
        "titulo": "Avaliação de Matemática - 9º Ano",
        "disciplina": "Matemática",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "turma": "Turma A",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "SÃO MIGUEL DOS CAMPOS",
        "estado": "ALAGOAS",
        "data_aplicacao": "2024-05-01T08:00:00.000Z",
        "status": "concluida",
        "total_alunos": 30,
        "alunos_participantes": 28,
        "alunos_pendentes": 1,
        "alunos_ausentes": 1,
        "media_nota": 7.8,
        "media_proficiencia": 255.0,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 2,
          "basico": 7,
          "adequado": 13,
          "avancado": 6
        }
      },
      {
        "id": "test-987fcdeb-51a2-43d1-b789-123456789abc",
        "titulo": "Avaliação de Português - 9º Ano",
        "disciplina": "Português",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "turma": "Turma A",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "SÃO MIGUEL DOS CAMPOS",
        "estado": "ALAGOAS",
        "data_aplicacao": "2024-05-02T08:00:00.000Z",
        "status": "concluida",
        "total_alunos": 30,
        "alunos_participantes": 27,
        "alunos_pendentes": 2,
        "alunos_ausentes": 1,
        "media_nota": 7.2,
        "media_proficiencia": 245.4,
        "distribuicao_classificacao": {
          "abaixo_do_basico": 3,
          "basico": 8,
          "adequado": 12,
          "avancado": 4
        }
      }
    ],
    "paginacao": {
      "page": 1,
      "per_page": 10,
      "total": 2,
      "total_pages": 1
    }
  },
  "opcoes_proximos_filtros": {
    "series": [
      { "id": "456e7890-f12g-34h5-i678-901234567890", "name": "9º Ano" }
    ],
    "turmas": [
      { "id": "abc123-def456-ghi789", "name": "Turma A" }
    ]
  }
}
```

## Níveis de Granularidade

A rota determina automaticamente o nível de granularidade baseado nos filtros aplicados:

1. **estado**: Quando apenas estado é fornecido
2. **municipio**: Quando estado e município são fornecidos
3. **escola**: Quando escola é especificada
4. **serie**: Quando série é especificada
5. **turma**: Quando turma é especificada
6. **avaliacao**: Quando avaliação específica é fornecida

## Opções dos Próximos Filtros

O campo `opcoes_proximos_filtros` fornece as opções disponíveis para os próximos filtros baseado no nível de granularidade atual:

- **escolas**: Lista de escolas disponíveis no escopo atual
- **series**: Lista de séries disponíveis no escopo atual
- **turmas**: Lista de turmas disponíveis no escopo atual
- **avaliacoes**: Lista de avaliações disponíveis no escopo atual

## Códigos de Status

- `200`: Sucesso
- `400`: Erro de validação (mínimo 2 filtros obrigatórios)
- `401`: Não autorizado (token inválido)
- `403`: Acesso negado (role insuficiente)
- `500`: Erro interno do servidor

## Observações

1. A rota retorna apenas avaliações que foram efetivamente aplicadas (estão na tabela `class_test`)
2. As estatísticas são calculadas em tempo real baseadas nos dados disponíveis
3. A paginação é aplicada apenas aos resultados detalhados
4. As opções dos próximos filtros são filtradas dinamicamente baseadas no escopo atual
5. Professores veem apenas suas próprias avaliações 