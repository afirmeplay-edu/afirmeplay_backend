# Rota de Avaliações - Sistema de Filtros em Cascata

## Visão Geral

A rota `/avaliacoes` foi modificada para implementar um sistema de filtros em cascata que permite navegar hierarquicamente pelos dados de avaliação, desde o nível municipal até o nível de turma específica.

## Endpoint

```
GET /avaliacoes
```

## Autenticação

A rota requer autenticação JWT e as seguintes permissões:
- `admin`
- `professor` 
- `coordenador`
- `diretor`
- `aluno`

## Parâmetros de Query

### Filtros Obrigatórios (mínimo 3)

| Parâmetro | Tipo | Descrição | Obrigatório |
|-----------|------|-----------|-------------|
| `estado` | string | Nome do estado | ✅ |
| `municipio` | string | Nome do município | ✅ |
| `avaliacao` | string | ID da avaliação | ✅ |
| `escola` | string | ID da escola | ❌ |
| `serie` | string | ID da série/ano | ❌ |
| `turma` | string | ID da turma | ❌ |

### Parâmetros de Paginação

| Parâmetro | Tipo | Descrição | Padrão |
|-----------|------|-----------|--------|
| `page` | integer | Número da página | 1 |
| `per_page` | integer | Itens por página | 10 |

## Sistema de Filtros em Cascata

### Níveis de Granularidade

A rota determina automaticamente o nível de granularidade baseado nos filtros aplicados:

1. **Município** (`estado` + `municipio` + `avaliacao`)
2. **Escola** (`estado` + `municipio` + `avaliacao` + `escola`)
3. **Série** (`estado` + `municipio` + `avaliacao` + `escola` + `serie`)
4. **Turma** (`estado` + `municipio` + `avaliacao` + `escola` + `serie` + `turma`)

### Lógica de Cálculo por Nível

- **Município**: Média de todas as séries e turmas onde a avaliação foi aplicada no município
- **Escola**: Média de todas as séries e turmas da escola específica
- **Série**: Média de todas as turmas da série específica
- **Turma**: Resultados específicos da turma

## Exemplos de Uso

### 1. Nível Municipal

```bash
GET /avaliacoes?estado=São Paulo&municipio=São Paulo&avaliacao=123&page=1&per_page=10
```

**Resposta:**
```json
{
  "nivel_granularidade": "municipio",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "São Paulo", 
    "escola": null,
    "serie": null,
    "turma": null,
    "avaliacao": "123"
  },
  "estatisticas_gerais": {
    "tipo": "municipio",
    "nome": "São Paulo",
    "estado": "São Paulo",
    "total_escolas": 15,
    "total_series": 45,
    "total_turmas": 120,
    "total_avaliacoes": 1,
    "total_alunos": 3600,
    "alunos_participantes": 3200,
    "alunos_pendentes": 400,
    "alunos_ausentes": 400,
    "media_nota_geral": 7.5,
    "media_proficiencia_geral": 750.0,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 200,
      "basico": 800,
      "adequado": 1500,
      "avancado": 700
    }
  },
  "resultados_por_disciplina": [
    {
      "disciplina": "Matemática",
      "total_avaliacoes": 1,
      "total_alunos": 3600,
      "alunos_participantes": 3200,
      "alunos_pendentes": 400,
      "media_nota": 7.5,
      "media_proficiencia": 750.0,
      "distribuicao_classificacao": {
        "abaixo_do_basico": 200,
        "basico": 800,
        "adequado": 1500,
        "avancado": 700
      }
    }
  ],
  "resultados_detalhados": {
    "avaliacoes": [...],
    "paginacao": {
      "page": 1,
      "per_page": 10,
      "total": 1,
      "total_pages": 1
    }
  },
  "opcoes_proximos_filtros": {
    "escolas": [
      {"id": "456", "name": "Escola Municipal A"},
      {"id": "789", "name": "Escola Municipal B"}
    ]
  }
}
```

### 2. Nível Escola

```bash
GET /avaliacoes?estado=São Paulo&municipio=São Paulo&avaliacao=123&escola=456&page=1&per_page=10
```

**Resposta:**
```json
{
  "nivel_granularidade": "escola",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "escola": "456",
    "serie": null,
    "turma": null,
    "avaliacao": "123"
  },
  "estatisticas_gerais": {
    "tipo": "escola",
    "nome": "Escola Municipal A",
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "total_series": 3,
    "total_turmas": 8,
    "total_avaliacoes": 1,
    "total_alunos": 240,
    "alunos_participantes": 220,
    "alunos_pendentes": 20,
    "alunos_ausentes": 20,
    "media_nota_geral": 7.8,
    "media_proficiencia_geral": 780.0,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 10,
      "basico": 50,
      "adequado": 120,
      "avancado": 40
    }
  },
  "opcoes_proximos_filtros": {
    "series": [
      {"id": "1", "name": "1º Ano"},
      {"id": "2", "name": "2º Ano"},
      {"id": "3", "name": "3º Ano"}
    ]
  }
}
```

### 3. Nível Série

```bash
GET /avaliacoes?estado=São Paulo&municipio=São Paulo&avaliacao=123&escola=456&serie=1&page=1&per_page=10
```

**Resposta:**
```json
{
  "nivel_granularidade": "serie",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "escola": "456",
    "serie": "1",
    "turma": null,
    "avaliacao": "123"
  },
  "estatisticas_gerais": {
    "tipo": "serie",
    "nome": "1º Ano",
    "escola": "Escola Municipal A",
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "total_turmas": 3,
    "total_avaliacoes": 1,
    "total_alunos": 90,
    "alunos_participantes": 85,
    "alunos_pendentes": 5,
    "alunos_ausentes": 5,
    "media_nota_geral": 8.0,
    "media_proficiencia_geral": 800.0,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 2,
      "basico": 15,
      "adequado": 45,
      "avancado": 23
    }
  },
  "opcoes_proximos_filtros": {
    "turmas": [
      {"id": "101", "name": "1º Ano A"},
      {"id": "102", "name": "1º Ano B"},
      {"id": "103", "name": "1º Ano C"}
    ]
  }
}
```

### 4. Nível Turma

```bash
GET /avaliacoes?estado=São Paulo&municipio=São Paulo&avaliacao=123&escola=456&serie=1&turma=101&page=1&per_page=10
```

**Resposta:**
```json
{
  "nivel_granularidade": "turma",
  "filtros_aplicados": {
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "escola": "456",
    "serie": "1",
    "turma": "101",
    "avaliacao": "123"
  },
  "estatisticas_gerais": {
    "tipo": "turma",
    "nome": "1º Ano A",
    "serie": "1º Ano",
    "escola": "Escola Municipal A",
    "estado": "São Paulo",
    "municipio": "São Paulo",
    "total_avaliacoes": 1,
    "total_alunos": 30,
    "alunos_participantes": 28,
    "alunos_pendentes": 2,
    "alunos_ausentes": 2,
    "media_nota_geral": 8.2,
    "media_proficiencia_geral": 820.0,
    "distribuicao_classificacao_geral": {
      "abaixo_do_basico": 0,
      "basico": 5,
      "adequado": 15,
      "avancado": 8
    }
  },
  "opcoes_proximos_filtros": {
    "maximo_alcancado": true
  }
}
```

## Estrutura da Resposta

### Campos Principais

- **`nivel_granularidade`**: Indica o nível atual (municipio, escola, serie, turma)
- **`filtros_aplicados`**: Lista todos os filtros atualmente aplicados
- **`estatisticas_gerais`**: Estatísticas consolidadas do nível atual
- **`resultados_por_disciplina`**: Estatísticas separadas por disciplina
- **`resultados_detalhados`**: Lista paginada das avaliações com detalhes
- **`opcoes_proximos_filtros`**: Opções disponíveis para o próximo nível

### Campos das Estatísticas

- **`total_alunos`**: Total de alunos no escopo
- **`alunos_participantes`**: Alunos que realizaram a avaliação
- **`alunos_pendentes`**: Alunos que não realizaram
- **`alunos_ausentes`**: Alunos ausentes
- **`media_nota_geral`**: Média das notas (0-10)
- **`media_proficiencia_geral`**: Média da proficiência (0-1000)
- **`distribuicao_classificacao_geral`**: Distribuição por nível de proficiência

## Validações

### Erros Comuns

1. **Filtros insuficientes**:
```json
{
  "error": "É necessário aplicar pelo menos 3 filtros (estado, municipio, escola, serie, turma, avaliacao)"
}
```

2. **Estado obrigatório**:
```json
{
  "error": "Estado é obrigatório como primeiro filtro"
}
```

3. **Município obrigatório**:
```json
{
  "error": "Município é obrigatório como segundo filtro"
}
```

4. **Avaliação obrigatória**:
```json
{
  "error": "Avaliação é obrigatória como terceiro filtro"
}
```

## Implementação Frontend

### Fluxo de Navegação

1. **Selecionar Estado** → Retorna municípios disponíveis
2. **Selecionar Município** → Retorna avaliações disponíveis
3. **Selecionar Avaliação** → Retorna estatísticas do município + escolas disponíveis
4. **Selecionar Escola** → Retorna estatísticas da escola + séries disponíveis
5. **Selecionar Série** → Retorna estatísticas da série + turmas disponíveis
6. **Selecionar Turma** → Retorna estatísticas específicas da turma

### Uso das Opções de Próximos Filtros

O campo `opcoes_proximos_filtros` contém as opções disponíveis para o próximo nível:

- **`escolas`**: Lista de escolas quando no nível municipal
- **`series`**: Lista de séries quando no nível escola
- **`turmas`**: Lista de turmas quando no nível série
- **`maximo_alcancado`**: `true` quando no nível máximo (turma)

## Notas Importantes

1. **Performance**: As consultas são otimizadas para cada nível de granularidade
2. **Cache**: Considere implementar cache para as opções de filtros
3. **Paginação**: Aplicada apenas aos resultados detalhados, não às estatísticas
4. **Permissões**: Professores só veem dados de suas escolas/turmas
5. **Dados Vazios**: Retorna estatísticas zeradas quando não há dados

## Exemplo de Implementação Frontend

```javascript
// Exemplo de como usar as opções de próximos filtros
async function carregarOpcoesFiltros(filtrosAtuais) {
  const response = await fetch(`/avaliacoes?${new URLSearchParams(filtrosAtuais)}`);
  const data = await response.json();
  
  // Atualizar estatísticas
  atualizarEstatisticas(data.estatisticas_gerais);
  
  // Atualizar opções de próximos filtros
  if (data.opcoes_proximos_filtros.escolas) {
    preencherSelectEscolas(data.opcoes_proximos_filtros.escolas);
  } else if (data.opcoes_proximos_filtros.series) {
    preencherSelectSeries(data.opcoes_proximos_filtros.series);
  } else if (data.opcoes_proximos_filtros.turmas) {
    preencherSelectTurmas(data.opcoes_proximos_filtros.turmas);
  }
}
``` 