# Integração com OpenAI para Análise de Relatórios

## Visão Geral

Este sistema integra com a OpenAI para gerar análises automáticas e contextualizadas dos relatórios de avaliação diagnóstica. A IA analisa os dados e gera textos com insights, alertas e recomendações específicas.

## Configuração

### 1. Dependências
```bash
pip install openai
```

### 2. Configuração da API
A chave da API está configurada em `app/config/openai_config.py`:
```python
OPENAI_API_KEY = "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"
```

### 3. Modelo e Configurações
- **Modelo**: GPT-4o-mini (econômico e eficiente)
- **Max Tokens**: 2000
- **Temperature**: 0.7 (balanceia criatividade e consistência)

## Como Funciona

### 1. Fluxo de Análise
1. **Coleta de Dados**: Sistema coleta dados completos do relatório
2. **Preparação**: Dados são organizados e formatados para a IA
3. **Análise**: OpenAI analisa os dados e gera insights
4. **Processamento**: Resposta é organizada em seções específicas
5. **Retorno**: Análise é retornada junto com o relatório

### 2. Pontos de Análise da IA

#### **Participação dos Alunos**
- Compara matriculados vs avaliados vs faltosos
- Gera alertas se faltosos > avaliados
- Recomenda estratégias de melhoria

#### **Proficiência**
- Compara com média municipal
- Identifica pontos fortes e fracos
- Sugere focos estratégicos

#### **Notas**
- Analisa padrões por disciplina
- Compara com referências
- Identifica áreas de melhoria

#### **Habilidades**
- Identifica habilidades ≥70% (dentro da meta)
- Identifica habilidades <70% (abaixo da meta)
- Destaque para habilidades críticas (<30%)
- Considera questões anuladas
- Sugere planos de recuperação

## Endpoints Disponíveis

### 1. Relatório com IA
```
GET /reports/relatorio-com-ia/<evaluation_id>
```
**Retorna**: Relatório completo + análise da IA

### 2. Relatório Completo (sem IA)
```
GET /reports/relatorio-completo/<evaluation_id>
```
**Retorna**: Relatório completo sem análise da IA

### 3. Relatório PDF
```
GET /reports/relatorio-pdf/<evaluation_id>
```
**Retorna**: PDF do relatório

## Estrutura dos Dados

### Dados Enviados para a IA
```json
{
  "avaliacao": {
    "id": "uuid",
    "titulo": "Título da Avaliação",
    "disciplinas": ["LP", "MAT"],
    "questoes_anuladas": ["Q10", "Q11"]
  },
  "total_alunos": {
    "total_geral": {
      "matriculados": 249,
      "avaliados": 222,
      "faltosos": 27,
      "percentual": 89.2
    }
  },
  "proficiencia": {
    "por_disciplina": {...},
    "media_municipal_por_disciplina": {...}
  },
  "nota_geral": {...},
  "acertos_por_habilidade": {...}
}
```

### Resposta da IA
```json
{
  "analise_ia": {
    "participacao_analise": "Texto sobre participação...",
    "proficiencia_analise": "Texto sobre proficiência...",
    "notas_analise": "Texto sobre notas...",
    "habilidades_analise": "Texto sobre habilidades...",
    "recomendacoes_gerais": "Recomendações gerais..."
  }
}
```

## Exemplos de Análise

### Participação
```
A escola avaliou 222 alunos do 9º ano, o que representa 89% do total de 249 alunos matriculados.
Registrou-se um total de 27 alunos faltosos. A taxa de participação de 89% é boa, indicando um bom
engajamento geral. Contudo, a ausência de 27 alunos é um número considerável. Recomenda-se a
investigação das causas dessas ausências, um contato proativo com as famílias para elevar a participação
em futuras avaliações e o planejamento de uma reposição diagnóstica para os alunos faltosos.
```

### Proficiência
```
A proficiência média da escola nesta avaliação diagnóstica foi de 298,86 em Língua Portuguesa e 268,29
em Matemática. Comparativamente, o desempenho em Língua Portuguesa (298,86) está significativamente 
acima da média de proficiência de 272,19 alcançada na Prova Saeb/2023 para o 9º ano. Este é um 
resultado excelente e um grande destaque para a escola, indicando um alto nível de domínio das 
competências em LP. Em Matemática, a proficiência de 268,29 encontra-se abaixo da média de 293,55 
obtida no Saeb/2023. Apesar de ser uma proficiência considerável, ainda há uma lacuna para atingir 
o referencial nacional, indicando que esta é a área que demanda maior foco estratégico.
```

## Testando a Integração

### 1. Teste Básico
```bash
python test_ai_integration.py
```

### 2. Teste via API
```bash
# Com autenticação JWT
curl -H "Authorization: Bearer <token>" \
     http://localhost:5000/reports/relatorio-com-ia/<evaluation_id>
```

## Tratamento de Erros

### 1. Falha na API OpenAI
- Sistema retorna textos padrão
- Log de erro é registrado
- Funcionalidade básica continua funcionando

### 2. Dados Insuficientes
- IA recebe dados disponíveis
- Gera análise baseada no que tem
- Indica limitações quando necessário

### 3. Rate Limiting
- Configuração de retry automático
- Fallback para análise básica
- Monitoramento de uso da API

## Monitoramento e Logs

### 1. Logs de Sucesso
```
INFO: Análise da IA concluída para avaliação <id>
INFO: OpenAI respondeu em <tempo>ms
```

### 2. Logs de Erro
```
ERROR: Falha na chamada OpenAI: <erro>
ERROR: Dados insuficientes para análise: <detalhes>
```

### 3. Métricas
- Tempo de resposta da IA
- Taxa de sucesso
- Uso de tokens
- Custos estimados

## Próximos Passos

### 1. Melhorias Planejadas
- Cache de análises similares
- Análise incremental (só mudanças)
- Personalização por tipo de escola
- Integração com outros modelos de IA

### 2. Otimizações
- Batching de requisições
- Compressão de prompts
- Análise assíncrona
- Cache inteligente

## Suporte

Para dúvidas ou problemas:
1. Verificar logs do sistema
2. Testar conexão com OpenAI
3. Validar dados de entrada
4. Consultar documentação da API OpenAI
