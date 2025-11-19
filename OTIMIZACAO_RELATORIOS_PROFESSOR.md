# Otimização de Relatórios para Professores

## Resumo

Esta documentação descreve as mudanças implementadas para resolver o problema de timeout nos relatórios de avaliações quando professores acessam os dados. A solução implementa um sistema de cache específico por professor, evitando o cálculo completo da escola toda vez que um professor acessa o relatório.

## Problema Identificado

### Situação Anterior

1. **Timeout no Frontend**: Quando professores acessavam relatórios, o sistema calculava os dados de toda a escola e depois filtrava em memória apenas as turmas do professor, causando timeout.

2. **Ineficiência**: O sistema tinha cache apenas para escopos `overall`, `city` e `school`, mas não para professores individuais.

3. **Filtro em Memória**: A função `_filtrar_payload_por_turmas_professor` filtrava dados já calculados, mas o cálculo inicial era muito lento.

## Solução Implementada

### 1. Novo Escopo `teacher` no Cache

Foi adicionado suporte ao escopo `teacher` na tabela `report_aggregates`, permitindo cache específico por professor.

**Arquivo**: `app/services/report_aggregate_service.py`

```python
def _normalize_scope(scope_type: str, scope_id: Optional[str]) -> tuple[str, Optional[str]]:
    scope_type = (scope_type or "overall").lower()
    if scope_type not in {"overall", "city", "school", "teacher"}:  # Adicionado "teacher"
        # ...
```

### 2. Marcação de Cache como Dirty para Professores

Quando um aluno responde uma avaliação, o sistema agora identifica todos os professores vinculados às turmas do aluno e marca seus caches como "dirty".

**Arquivo**: `app/services/evaluation_result_service.py`

```python
# Marcar dirty para professores vinculados às turmas do aluno
if class_identifier:
    from app.models.teacherClass import TeacherClass
    
    # Buscar professores vinculados à turma do aluno
    teacher_classes = TeacherClass.query.filter_by(class_id=class_identifier).all()
    teacher_ids = [tc.teacher_id for tc in teacher_classes]
    
    # Marcar dirty para cada professor
    for teacher_id in teacher_ids:
        ReportAggregateService.mark_dirty(test_id, 'teacher', teacher_id, commit=False)
```

### 3. Determinação Automática de Escopo por Role

Foi criada a função `_determinar_escopo_por_role` que determina automaticamente o escopo correto baseado no role do usuário.

**Arquivo**: `app/routes/report_routes.py`

**Mapeamento de Roles para Escopos**:

| Role | Escopo | scope_id |
|------|--------|----------|
| **Admin** | `overall`, `city` ou `school` | Conforme parâmetros fornecidos |
| **Tecadm** | `city` | `city_id` do tecadm |
| **Diretor/Coordenador** | `school` | `school_id` do manager |
| **Professor** | `teacher` | `teacher_id` do professor |

### 4. Função Específica para Cálculo por Turmas

Foi criada a função `_montar_resposta_relatorio_por_turmas` que calcula o relatório apenas para um conjunto específico de turmas, otimizando o cálculo para professores.

**Arquivo**: `app/routes/report_routes.py`

Esta função:
- Recebe uma lista específica de `ClassTest`
- Calcula apenas os dados dessas turmas
- Retorna o mesmo formato de dados que a função original

### 5. Modificação das Rotas de Relatório

As rotas `dados_json` e `relatorio_pdf` foram modificadas para:

1. **Determinar escopo automaticamente** baseado no role do usuário
2. **Usar cache específico** para cada role
3. **Calcular apenas dados necessários** (professores veem apenas suas turmas)

**Arquivo**: `app/routes/report_routes.py`

**Antes**:
```python
# Calculava escola inteira e filtrava depois
resposta = ReportAggregateService.ensure_payload(...)
if user_role == 'professor':
    resposta = _filtrar_payload_por_turmas_professor(resposta, teacher_class_ids)
```

**Depois**:
```python
# Determina escopo correto e calcula apenas o necessário
scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
if scope_type == 'teacher':
    # Calcula apenas turmas do professor
    class_tests = ClassTest.query.filter(...).all()
    resposta = ReportAggregateService.ensure_payload(
        evaluation_id, 'teacher', teacher.id, build_payload
    )
```

## Benefícios

### Performance

- **Redução drástica de tempo**: Professores agora veem apenas dados de suas turmas, não da escola inteira
- **Cache específico**: Cada professor tem seu próprio cache, evitando recálculos desnecessários
- **Escalabilidade**: Sistema suporta muitos professores sem degradação de performance

### Consistência

- **Mesma estrutura**: Todos os roles usam a mesma estrutura de cache
- **Manutenibilidade**: Lógica centralizada e fácil de entender
- **Compatibilidade**: Escopos existentes (`overall`, `city`, `school`) continuam funcionando

### Experiência do Usuário

- **Sem timeout**: Professores não enfrentam mais timeout ao acessar relatórios
- **Resposta rápida**: Dados são servidos instantaneamente quando estão em cache
- **Dados corretos**: Professores veem apenas dados de suas turmas, como esperado

## Estrutura de Cache

### Tabela `report_aggregates`

A tabela agora suporta os seguintes escopos:

- `overall`: Dados de todas as turmas da avaliação
- `city`: Dados de todas as turmas de um município
- `school`: Dados de todas as turmas de uma escola
- `teacher`: Dados apenas das turmas de um professor específico

### Chave Única

Cada registro é identificado por:
- `test_id`: ID da avaliação
- `scope_type`: Tipo de escopo (`overall`, `city`, `school`, `teacher`)
- `scope_id`: ID do escopo (ou `NULL` para `overall`)

### Flag `is_dirty`

Quando um aluno responde:
- `overall` é marcado como dirty
- `city` da escola do aluno é marcado como dirty
- `school` da escola do aluno é marcado como dirty
- `teacher` de cada professor vinculado às turmas do aluno é marcado como dirty

## Fluxo de Dados

### Quando Aluno Responde

1. Aluno submete respostas
2. Sistema calcula resultado do aluno
3. Sistema identifica:
   - Escola do aluno → marca `school` como dirty
   - Município da escola → marca `city` como dirty
   - Professores das turmas do aluno → marca `teacher` de cada um como dirty
4. Sistema marca `overall` como dirty

### Quando Usuário Acessa Relatório

1. Sistema identifica role do usuário
2. Sistema determina escopo correto (`_determinar_escopo_por_role`)
3. Sistema verifica cache:
   - Se existe e não está dirty → retorna cache
   - Se não existe ou está dirty → calcula e salva no cache
4. Sistema retorna dados

## Considerações

### Espaço em Disco

- **Mais registros**: Cada professor por avaliação cria um registro adicional na tabela
- **Impacto**: Geralmente baixo, pois professores são limitados por avaliação
- **Otimização futura**: Pode ser implementada limpeza de caches antigos

### Atualização de Cache

- **Múltiplos professores**: Quando um aluno responde, todos os professores da turma têm cache marcado como dirty
- **Recálculo**: Na próxima vez que cada professor acessar, o cache será recalculado
- **Eficiência**: Recálculo é rápido pois calcula apenas turmas do professor

### Compatibilidade

- **Backward compatible**: Escopos existentes continuam funcionando
- **Sem breaking changes**: Mudanças são transparentes para outros roles
- **Migração**: Não requer migração de dados, apenas código

## Arquivos Modificados

1. `app/services/report_aggregate_service.py`
   - Adicionado suporte ao escopo `teacher`

2. `app/services/evaluation_result_service.py`
   - Adicionada lógica para marcar professores como dirty quando aluno responde

3. `app/routes/report_routes.py`
   - Criada função `_determinar_escopo_por_role`
   - Criada função `_montar_resposta_relatorio_por_turmas`
   - Modificadas rotas `dados_json` e `relatorio_pdf`

## Testes Recomendados

1. **Teste de Performance**
   - Acessar relatório como professor antes e depois das mudanças
   - Verificar redução de tempo de resposta

2. **Teste de Cache**
   - Acessar relatório como professor
   - Verificar criação de registro na tabela `report_aggregates` com `scope_type='teacher'`
   - Acessar novamente e verificar uso do cache

3. **Teste de Atualização**
   - Aluno responde avaliação
   - Verificar marcação de cache do professor como dirty
   - Professor acessa relatório e verifica recálculo

4. **Teste de Roles**
   - Verificar que admin, tecadm, diretor e coordenador continuam funcionando
   - Verificar que cada role usa o escopo correto

## Próximos Passos (Opcional)

1. **Limpeza de Cache**: Implementar job para limpar caches antigos
2. **Métricas**: Adicionar logging de performance para monitorar melhorias
3. **Otimização**: Considerar cache compartilhado entre professores da mesma escola (se necessário)

## Conclusão

A implementação do escopo `teacher` resolve o problema de timeout para professores, mantendo a mesma estrutura de cache para todos os roles. A solução é escalável, mantém compatibilidade com código existente e melhora significativamente a experiência do usuário.

