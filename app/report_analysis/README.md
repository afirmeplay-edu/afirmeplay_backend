# Report Analysis - Processamento Assíncrono de Relatórios

## Visão Geral

Este módulo implementa processamento assíncrono de relatórios educacionais usando Celery e Redis. Todas as operações pesadas (cálculos e análise de IA) são executadas em background, permitindo que as rotas HTTP retornem rapidamente.

## Estrutura

```
app/report_analysis/
├── __init__.py           # Exports principais
├── celery_app.py         # Configuração do Celery
├── debounce.py           # Serviço de debounce (Redis)
├── services.py           # ReportAggregateService (refatorado)
├── calculations.py       # Funções de cálculo (importadas do report_routes)
├── tasks.py             # Tasks Celery
├── routes.py            # Rotas refatoradas (assíncronas)
└── README.md            # Este arquivo
```

## Componentes

### 1. Celery App (`celery_app.py`)

Configuração do Celery com integração Flask. Usa Redis como broker e backend.

**Variáveis de ambiente:**
- `CELERY_BROKER_URL`: URL do Redis para broker (padrão: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: URL do Redis para resultados (padrão: `redis://localhost:6379/0`)

### 2. Debounce Service (`debounce.py`)

Evita múltiplas tasks simultâneas para o mesmo relatório usando Redis.

**Funcionalidades:**
- `should_trigger_rebuild()`: Verifica se deve disparar rebuild (com debounce)
- `clear_debounce()`: Remove debounce manualmente
- `get_remaining_ttl()`: Retorna TTL restante

**TTL padrão:** 60 segundos

### 3. Report Aggregate Service (`services.py`)

Serviço refatorado que **não executa mais cálculos**. Apenas:
- Consulta cache
- Salva resultados
- Gerencia flags `is_dirty` e `ai_analysis_is_dirty`

**Métodos principais:**
- `get_status()`: Retorna status do relatório ('ready', 'processing', 'not_found')
- `get_payload()`: Retorna payload do cache (ou None se dirty)
- `get_ai_analysis()`: Retorna análise de IA do cache (ou None se dirty)
- `save_payload()`: Salva payload no cache
- `save_ai_analysis()`: Salva análise de IA no cache

### 4. Tasks Celery (`tasks.py`)

Tasks que executam processamento pesado em background:

**`rebuild_report_for_scope(test_id, scope_type, scope_id)`**
- Recalcula todos os dados para um escopo específico
- Gera análise de IA
- Salva no cache
- Retry automático em caso de falha

**`rebuild_reports_for_test(test_id)`**
- Agenda rebuild para todos os escopos de uma avaliação
- Usa debounce para evitar múltiplas execuções

**`trigger_rebuild_if_needed(test_id, scope_type, scope_id)`**
- Verifica se precisa rebuild
- Usa debounce
- Agenda task se necessário

### 5. Routes (`routes.py`)

Rotas refatoradas que **não executam cálculos**:

**`GET /reports/dados-json/<evaluation_id>`**
- Retorna HTTP 200 se relatório está pronto
- Retorna HTTP 202 se está sendo processado
- Dispara task automaticamente se necessário

**`GET /reports/status/<evaluation_id>`**
- Retorna apenas status do relatório (útil para polling)

## Fluxo de Funcionamento

### 1. Quando um aluno responde

```
Aluno submete resposta
  ↓
EvaluationResultService.calculate_and_save()
  ├─ Calcula nota/proficiência
  ├─ Marca ReportAggregate como dirty (todos os escopos)
  └─ Dispara task: rebuild_reports_for_test.delay(test_id)
      ↓
Task Celery (background)
  ├─ Verifica debounce
  ├─ Para cada escopo dirty:
  │   ├─ Executa cálculos (_calcular_*)
  │   ├─ Salva payload
  │   ├─ Gera análise de IA
  │   └─ Salva ai_analysis
  └─ Marca is_dirty = False
```

### 2. Quando usuário acessa relatório

```
GET /reports/dados-json/<evaluation_id>
  ↓
Verifica status do ReportAggregate
  ├─ Se ready → Retorna dados (HTTP 200)
  └─ Se dirty/not_found:
      ├─ Dispara task (com debounce)
      └─ Retorna HTTP 202 (processing)
```

## Configuração

### 1. Instalar dependências

```bash
pip install celery redis
```

### 2. Configurar Redis

Adicionar ao `.env`:
```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_URL=redis://localhost:6379/0
```

### 3. Iniciar Celery Worker

```bash
celery -A app.report_analysis.celery_app worker --loglevel=info
```

Ou com Flask app context:
```bash
celery -A app.report_analysis.celery_app:celery_app worker --loglevel=info
```

### 4. Monitorar tasks (opcional)

```bash
celery -A app.report_analysis.celery_app flower
```

## Migração

### Antes (Síncrono)

```python
# Rotas executavam cálculos diretamente
resposta = ReportAggregateService.ensure_payload(
    test_id, scope_type, scope_id,
    build_payload  # ⚠️ Executava cálculos (15-30s)
)
```

### Depois (Assíncrono)

```python
# Rotas apenas consultam cache
status = ReportAggregateService.get_status(test_id, scope_type, scope_id)
if status['status'] != 'ready':
    trigger_rebuild_if_needed.delay(test_id, scope_type, scope_id)
    return jsonify({"status": "processing"}), 202
```

## Troubleshooting

### Redis não disponível

O sistema funciona mesmo sem Redis, mas:
- Debounce não funciona (múltiplas tasks podem ser agendadas)
- Tasks ainda funcionam se Celery estiver configurado

### Celery não inicializa

Verificar:
1. Redis está rodando?
2. Variáveis de ambiente configuradas?
3. Dependências instaladas?

### Tasks não executam

Verificar:
1. Celery worker está rodando?
2. Logs do worker mostram erros?
3. Tasks estão sendo agendadas? (verificar logs da aplicação)

## Próximos Passos

1. Mover funções `_calcular_*` de `report_routes.py` para `calculations.py`
2. Adicionar monitoramento de tasks (Flower)
3. Implementar WebSocket para notificar frontend quando relatório estiver pronto
4. Adicionar métricas de performance

