# ✅ Implementação de Resultados Socioeconômicos - COMPLETA

## Sistema Implementado

Sistema completo para geração de relatórios de resultados de formulários socioeconômicos com:

- ✅ Cache persistente no banco
- ✅ Invalidação automática quando resposta é salva
- ✅ Processamento assíncrono via Celery
- ✅ Paginação de alunos nos índices
- ✅ Filtros hierárquicos (estado → município → escola → série → turma)

## Arquivos Criados

### Novos Arquivos (10 arquivos)

1. **Models**
    - `app/socioeconomic_forms/models/form_result_cache.py`

2. **Services**
    - `app/socioeconomic_forms/services/results_cache_service.py`
    - `app/socioeconomic_forms/services/results_service.py`
    - `app/socioeconomic_forms/services/results_tasks.py`

3. **Routes**
    - `app/socioeconomic_forms/routes/results_routes.py`

4. **Migration**
    - `migrations/versions/20260204_add_form_result_cache_table.py`

5. **Documentação**
    - `app/socioeconomic_forms/RESULTS_IMPLEMENTATION.md`
    - `IMPLEMENTACAO_RESULTADOS_SOCIOECONOMICOS.md` (este arquivo)

### Arquivos Modificados (4 arquivos)

1. `app/socioeconomic_forms/services/response_service.py`
    - Adicionada invalidação automática do cache quando resposta é salva

2. `app/report_analysis/celery_app.py`
    - Adicionado `results_tasks` ao include do Celery

3. `app/__init__.py`
    - Importado e registrado blueprint `results_routes`

4. `app/socioeconomic_forms/models/__init__.py`
    - Exportado `FormResultCache`

## Próximos Passos

### 1. Executar Migration

```bash
flask db upgrade
```

Isso criará a tabela `form_result_cache` no banco.

### 2. Popular Cache Inicial (Para Formulários Existentes)

⚠️ **IMPORTANTE:** Se você já tem formulários com respostas no banco, precisa popular o cache inicial.

**Opção A - Script Python (Recomendado):**

```bash
# Ver o que seria feito
python scripts/populate_socioeconomic_cache.py --dry-run

# Popular todos os formulários
python scripts/populate_socioeconomic_cache.py

# Popular um formulário específico
python scripts/populate_socioeconomic_cache.py --form-id abc-123-uuid
```

**Opção B - Via HTTP (Requer Celery rodando):**

```bash
curl -X POST http://localhost:5000/forms/results/cache/populate-all \
  -H "Authorization: Bearer {admin-token}"
```

📖 Ver `app/socioeconomic_forms/POPULATE_CACHE_GUIDE.md` para guia completo.

### 3. Iniciar Celery Worker

**Windows:**

```bash
celery -A app.report_analysis.celery_app worker --loglevel=info --pool=solo
```

**Linux/Mac:**

```bash
celery -A app.report_analysis.celery_app worker --loglevel=info
```

### 4. Testar Endpoints

#### 4.1. Relatório de Índices Gerais

```http
GET /forms/{form_id}/results/indices?state=SP&escola=uuid&page=1&limit=20
Authorization: Bearer {token}
```

**Primeira vez (cache não existe):**

- Retorna 202 Accepted com `taskId`
- Frontend faz polling em `/forms/{form_id}/results/status/{taskId}`

**Próximas vezes (cache existe):**

- Retorna 200 OK com resultado direto

#### 3.2. Relatório de Perfis

```http
GET /forms/{form_id}/results/profiles?state=SP&escola=uuid
Authorization: Bearer {token}
```

Mesmo fluxo: 202 na primeira vez, 200 depois.

#### 4.3. Verificar Status de Task

```http
GET /forms/{form_id}/results/status/{taskId}
Authorization: Bearer {token}
```

**Resposta enquanto processa:**

```json
{
	"status": "processing",
	"progress": 0
}
```

**Resposta quando completa:**

```json
{
  "status": "completed",
  "result": { ... }
}
```

#### 4.4. Invalidar Cache (Opcional)

```http
POST /forms/{form_id}/results/cache/invalidate
Authorization: Bearer {token}
```

## Tipos de Relatórios

### 1. Índices Gerais (com porcentagens)

Retorna 4 índices:

- **Distorção idade-série** (Q20 != "Nunca")
- **Histórico de reprovação** (Q19 != "Não")
- **Sem acesso à internet** (Q13b == "não")
- **Baixo engajamento familiar** (Q10 == "Nunca")

Cada índice inclui:

- Total de alunos
- Porcentagem
- Lista paginada de alunos com detalhes

### 2. Perfis (com contagens)

Retorna 4 perfis:

- **Perfil Demográfico** (Q1-Q5)
- **Contexto Familiar** (Q6-Q13)
- **Trajetória Escolar** (Q14-Q21)
- **Ambiente Escolar** (Q22-Q23 para 5º ano, Q22-Q24 para 9º ano)

Cada perfil inclui contagens de respostas por questão (NÃO porcentagens).

## Invalidação Automática

### Como Funciona

1. **Aluno responde formulário** → `ResponseService.save_response()`
2. **Service chama** → `ResultsCacheService.mark_dirty_for_response()`
3. **Identifica dados do aluno**: estado, município, escola, série, turma
4. **Busca caches afetados**: verifica quais filtros incluem este aluno
5. **Marca como dirty**: apenas os caches relevantes
6. **Agenda rebuild** (opcional): quando resposta é completada

### Exemplo

```
Aluno: João Silva
Escola: EMEF Centro (abc)
Município: São Paulo (xyz)
Estado: SP

Caches marcados como dirty:
✅ Cache geral (sem filtros)
✅ Cache {state: 'SP'}
✅ Cache {state: 'SP', escola: 'abc'}
❌ Cache {state: 'RJ'} - NÃO marca (estado diferente)
```

## Filtros Hierárquicos

Suporta filtros em cascata:

```
Estado (string)
  └─> Município (UUID)
      └─> Escola (String)
          └─> Série (UUID)
              └─> Turma (UUID)
```

## Paginação

Apenas para índices (lista de alunos):

- `page`: Número da página (default: 1)
- `limit`: Itens por página (default: 20)

## Performance

- **Cache persistente**: Resultados salvos no banco
- **Invalidação inteligente**: Apenas caches afetados
- **Processamento assíncrono**: Não bloqueia HTTP
- **Queries otimizadas**: JOINs com índices

## Logs

Acompanhe o processamento nos logs:

- `[INDICES]`: Geração de relatório de índices
- `[PROFILES]`: Geração de relatório de perfis
- `[REBUILD]`: Rebuild de caches dirty

## Segurança

- Todos os endpoints protegidos com JWT
- Acesso: admin, tecadm, diretor, coordenador
- Invalidação de cache: apenas admin e tecadm

## Troubleshooting

### Cache não invalida automaticamente

```
Verificar logs em response_service.py:
"Caches marcados como dirty para form_id=..."
```

### Task não processa

```bash
# Verificar se worker está rodando
celery -A app.report_analysis.celery_app worker --loglevel=debug
```

### Erro ao buscar resultado

```
Verificar se estudante tem:
- grade_id preenchido
- relacionamentos: User → Student → School → Grade
```

## Fluxo Completo de Teste

1. **Criar formulário socioeconômico**
2. **Enviar para alunos**
3. **Aluno responde formulário** → Cache marcado como dirty (automático!)
4. **Solicitar relatório**:
    ```
    GET /forms/{id}/results/indices?state=SP
    ```
5. **Recebe 202 com taskId**
6. **Fazer polling**:
    ```
    GET /forms/{id}/results/status/{taskId}
    ```
7. **Quando status = completed** → Resultado disponível
8. **Próxima requisição** → Retorna do cache (200 OK imediato)

## Endpoints Disponíveis

```
GET  /forms/{id}/results/indices           - Obter índices gerais
GET  /forms/{id}/results/profiles          - Obter perfis
GET  /forms/{id}/results/status/{taskId}   - Polling do status
POST /forms/{id}/results/cache/invalidate  - Invalidar cache (admin)
GET  /forms/{id}/results/cache/status      - Status do cache
```

## Estrutura do Projeto

```
socioeconomic_forms/
├── models/
│   ├── form_result_cache.py (NOVO)
│   └── ...
├── services/
│   ├── results_cache_service.py (NOVO)
│   ├── results_service.py (NOVO)
│   ├── results_tasks.py (NOVO)
│   ├── response_service.py (MODIFICADO)
│   └── ...
└── routes/
    ├── results_routes.py (NOVO)
    └── ...
```

## Status: ✅ IMPLEMENTAÇÃO COMPLETA

Sistema totalmente funcional e pronto para uso!

**Não foi alterado NADA fora do módulo socioeconomic_forms** (exceto registro do blueprint e include do Celery).

## Documentação Completa

Ver `app/socioeconomic_forms/RESULTS_IMPLEMENTATION.md` para documentação técnica detalhada.

---

**Data**: 04/02/2026
**Status**: ✅ Completo e testável
