# Relatório Completo de Avaliações

## Endpoint: `/reports/relatorio-completo/<evaluation_id>`

Este endpoint gera um relatório completo de uma avaliação específica com todos os dados solicitados.

### Autenticação
- **Método**: GET
- **Autenticação**: JWT Token obrigatório
- **Permissões**: admin, professor, coordenador, diretor

### Parâmetros
- `evaluation_id` (path): ID da avaliação para gerar o relatório

### Exemplo de Uso
```bash
GET /reports/relatorio-completo/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer <jwt_token>
```

### Estrutura da Resposta

```json
{
  "avaliacao": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "titulo": "Avaliação Diagnóstica 2025.1",
    "descricao": "Avaliação diagnóstica do primeiro semestre",
    "disciplinas": ["Língua Portuguesa", "Matemática"]
  },
  "total_alunos": {
    "por_turma": [
      {
        "turma": "9º A",
        "matriculados": 38,
        "avaliados": 37,
        "percentual": 97.4,
        "faltosos": 1
      },
      {
        "turma": "9º B",
        "matriculados": 37,
        "avaliados": 37,
        "percentual": 100.0,
        "faltosos": 0
      }
    ],
    "total_geral": {
      "matriculados": 249,
      "avaliados": 222,
      "percentual": 89.2,
      "faltosos": 27
    }
  },
  "niveis_aprendizagem": {
    "por_turma": [
      {
        "turma": "9º A",
        "abaixo_do_basico": 0,
        "basico": 0,
        "adequado": 5,
        "avancado": 32,
        "total": 37
      },
      {
        "turma": "9º B",
        "abaixo_do_basico": 2,
        "basico": 2,
        "adequado": 3,
        "avancado": 30,
        "total": 37
      }
    ],
    "geral": {
      "abaixo_do_basico": 20,
      "basico": 27,
      "adequado": 45,
      "avancado": 130,
      "total": 222
    }
  },
  "proficiencia": {
    "por_turma": [
      {
        "turma": "9º A",
        "proficiencia": 348.00
      },
      {
        "turma": "9º B",
        "proficiencia": 324.00
      }
    ],
    "media_geral": 283.57,
    "media_municipal": 265.00
  },
  "nota_geral": {
    "por_turma": [
      {
        "turma": "9º A",
        "nota": 8.25
      },
      {
        "turma": "9º B",
        "nota": 7.45
      }
    ],
    "media_geral": 6.31,
    "media_municipal": 5.50
  },
  "acertos_por_habilidade": {
    "habilidades": [
      {
        "codigo": "9L1.1",
        "descricao": "Habilidade 9L1.1",
        "acertos": 67,
        "total": 100,
        "percentual": 67.1,
        "ranking": 1,
        "questoes": [
          {
            "numero": 1,
            "acertos": 67,
            "total": 100
          }
        ]
      },
      {
        "codigo": "9L1.2",
        "descricao": "Habilidade 9L1.2",
        "acertos": 62,
        "total": 100,
        "percentual": 62.0,
        "ranking": 2,
        "questoes": [
          {
            "numero": 3,
            "acertos": 69,
            "total": 100
          },
          {
            "numero": 4,
            "acertos": 53,
            "total": 100
          }
        ]
      }
    ]
  }
}
```

### Seções do Relatório

#### 1. Total de Alunos que Realizaram a Avaliação
- **por_turma**: Lista com dados de cada turma
  - `matriculados`: Total de alunos da turma
  - `avaliados`: Alunos que realizaram a avaliação
  - `percentual`: Percentual de participação
  - `faltosos`: Alunos que não realizaram
- **total_geral**: Soma de todas as turmas

#### 2. Níveis de Aprendizagem por Turma
- **por_turma**: Distribuição por turma
  - `abaixo_do_basico`: Quantidade de alunos
  - `basico`: Quantidade de alunos
  - `adequado`: Quantidade de alunos
  - `avancado`: Quantidade de alunos
  - `total`: Total de alunos da turma
- **geral**: Soma de todas as turmas

#### 3. Proficiência
- **por_turma**: Média de proficiência por turma
- **media_geral**: Média geral de todas as turmas
- **media_municipal**: Média de todas as escolas do município

#### 4. Nota Geral por Turma
- **por_turma**: Média de nota por turma (escala 0-10)
- **media_geral**: Média geral de todas as turmas
- **media_municipal**: Média municipal para comparação

#### 5. Acertos por Habilidade
- **habilidades**: Lista ordenada por percentual de acertos
  - `codigo`: Código da habilidade (ex: 9L1.1)
  - `descricao`: Descrição da habilidade
  - `acertos`: Total de acertos
  - `total`: Total de respostas
  - `percentual`: Percentual de acertos
  - `ranking`: Posição no ranking (1 = melhor)
  - `questoes`: Detalhes das questões da habilidade

### Códigos de Erro

- **404**: Avaliação não encontrada ou não aplicada em nenhuma turma
- **401**: Token JWT inválido ou ausente
- **403**: Usuário sem permissão
- **500**: Erro interno do servidor

### Observações

1. **Média Municipal**: Calculada considerando todas as escolas do município onde a avaliação foi aplicada
2. **Níveis de Aprendizagem**: Baseados na classificação já calculada no sistema
3. **Habilidades**: Mapeadas pelo código da habilidade de cada questão
4. **Ranking**: Ordenado por percentual de acertos (maior para menor)
5. **Dados em Tempo Real**: Todos os cálculos são feitos em tempo real baseados nos dados atuais

### Endpoint de Teste

Para verificar se o blueprint está funcionando:
```bash
GET /reports/test
```

Resposta esperada:
```json
{
  "message": "Blueprint de relatórios funcionando corretamente",
  "status": "success"
}
```
