# Exemplo Prático de Uso do Relatório Completo

## Pré-requisitos

1. **Servidor rodando**: `python run.py`
2. **Token JWT válido**: Faça login para obter o token
3. **ID de uma avaliação válida**: Que tenha sido aplicada em turmas

## Passo a Passo

### 1. Obter Token JWT

```bash
# Fazer login para obter o token
curl -X POST "http://localhost:5000/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "seu_email@exemplo.com",
    "password": "sua_senha"
  }'
```

Resposta esperada:
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user_id",
    "email": "seu_email@exemplo.com",
    "role": "admin"
  }
}
```

### 2. Testar o Endpoint de Relatórios

```bash
# Testar se o blueprint está funcionando
curl -X GET "http://localhost:5000/reports/test"
```

Resposta esperada:
```json
{
  "message": "Blueprint de relatórios funcionando corretamente",
  "status": "success"
}
```

### 3. Gerar Relatório Completo

```bash
# Substitua EVALUATION_ID pelo ID real da avaliação
curl -X GET "http://localhost:5000/reports/relatorio-completo/EVALUATION_ID" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

## Exemplo com Dados Reais

### Buscar Avaliações Disponíveis

Primeiro, você pode listar as avaliações disponíveis:

```bash
curl -X GET "http://localhost:5000/evaluation-results/avaliacoes?estado=SP&municipio=SAO_PAULO" \
  -H "Authorization: Bearer SEU_TOKEN_JWT"
```

### Gerar Relatório

```bash
# Exemplo com ID fictício (substitua pelo ID real)
curl -X GET "http://localhost:5000/reports/relatorio-completo/123e4567-e89b-12d3-a456-426614174000" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Estrutura de Resposta Esperada

O relatório retornará dados estruturados como nas imagens fornecidas:

### Total de Alunos
```json
{
  "total_alunos": {
    "por_turma": [
      {
        "turma": "9º A",
        "matriculados": 38,
        "avaliados": 37,
        "percentual": 97.4,
        "faltosos": 1
      }
    ],
    "total_geral": {
      "matriculados": 249,
      "avaliados": 222,
      "percentual": 89.2,
      "faltosos": 27
    }
  }
}
```

### Níveis de Aprendizagem
```json
{
  "niveis_aprendizagem": {
    "por_turma": [
      {
        "turma": "9º A",
        "abaixo_do_basico": 0,
        "basico": 0,
        "adequado": 5,
        "avancado": 32,
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
  }
}
```

### Proficiência
```json
{
  "proficiencia": {
    "por_turma": [
      {
        "turma": "9º A",
        "proficiencia": 348.00
      }
    ],
    "media_geral": 283.57,
    "media_municipal": 265.00
  }
}
```

### Nota Geral
```json
{
  "nota_geral": {
    "por_turma": [
      {
        "turma": "9º A",
        "nota": 8.25
      }
    ],
    "media_geral": 6.31,
    "media_municipal": 5.50
  }
}
```

### Acertos por Habilidade
```json
{
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
      }
    ]
  }
}
```

## Tratamento de Erros

### Avaliação não encontrada
```json
{
  "error": "Avaliação não encontrada"
}
```

### Avaliação sem turmas aplicadas
```json
{
  "error": "Avaliação não foi aplicada em nenhuma turma"
}
```

### Token inválido
```json
{
  "error": "Token inválido"
}
```

## Integração com Frontend

Para integrar com o frontend, você pode usar:

```javascript
// Exemplo em JavaScript
async function gerarRelatorio(evaluationId, token) {
  try {
    const response = await fetch(`/reports/relatorio-completo/${evaluationId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const relatorio = await response.json();
    
    // Usar os dados para montar as tabelas
    console.log('Relatório completo:', relatorio);
    
    return relatorio;
  } catch (error) {
    console.error('Erro ao gerar relatório:', error);
    throw error;
  }
}

// Uso
gerarRelatorio('evaluation_id', 'jwt_token')
  .then(relatorio => {
    // Montar tabelas com os dados
    montarTabelaTotalAlunos(relatorio.total_alunos);
    montarTabelaNiveisAprendizagem(relatorio.niveis_aprendizagem);
    montarTabelaProficiencia(relatorio.proficiencia);
    montarTabelaNotaGeral(relatorio.nota_geral);
    montarTabelaAcertosHabilidade(relatorio.acertos_por_habilidade);
  })
  .catch(error => {
    console.error('Erro:', error);
  });
```

## Observações Importantes

1. **Performance**: O endpoint faz múltiplas consultas ao banco de dados. Para grandes volumes, considere implementar cache.

2. **Dados em Tempo Real**: Todos os cálculos são feitos em tempo real baseados nos dados atuais do banco.

3. **Permissões**: Apenas usuários com roles específicos podem acessar o relatório.

4. **Validação**: O endpoint valida se a avaliação existe e se foi aplicada em turmas.

5. **Estrutura**: Os dados retornados seguem exatamente a estrutura solicitada para facilitar a montagem das tabelas no frontend.
