# Mudanças no Sistema de Timezone

## Resumo das Alterações

O sistema foi atualizado para usar o **fuso horário local do servidor** em vez de forçar o uso do fuso horário do Brasil. Isso resolve problemas de inconsistência quando o servidor é executado em diferentes regiões.

## Principais Mudanças

### 1. Arquivo `app/utils/timezone_utils.py`

**Antes:**
- Forçava o uso do fuso horário do Brasil (`America/Sao_Paulo`)
- Funções como `get_brazil_time()`, `convert_to_brazil_time()`

**Depois:**
- Detecta automaticamente o fuso horário local do servidor
- Funções como `get_local_time()`, `convert_to_local_time()`
- Mantém funções antigas para compatibilidade (marcadas como DEPRECATED)

### 2. Rotas Atualizadas

As seguintes rotas foram atualizadas para usar o timezone local:

- `POST /test/<test_id>/apply` - Aplicar avaliação
- `GET /test/my-class/tests` - Listar avaliações da minha classe
- `GET /test/class/<class_id>/tests/complete` - Obter avaliações completas
- `POST /test/<test_id>/start-session` - Iniciar sessão
- `GET /test/debug/dates/<test_id>` - Debug de datas
- `POST /student-answers/submit` - Submeter respostas
- `POST /student-answers/save-partial` - Salvar respostas parciais

### 3. Dockerfile

Adicionada configuração de timezone:
```dockerfile
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
```

### 4. Novos Endpoints de Debug

- `GET /test/debug/timezone` - Para verificar o timezone atual do servidor
- `GET /test/debug/availability/<test_id>` - Para verificar a lógica de disponibilidade de uma avaliação

## Correções de Timezone Implementadas

### Problema Identificado

O sistema estava apresentando inconsistências na verificação de disponibilidade de avaliações devido a problemas de conversão de timezone. Especificamente:

1. **Datas do banco sem timezone**: As datas salvas no banco de dados não tinham informação de timezone
2. **Comparações incorretas**: As comparações de tempo estavam sendo feitas entre datas com timezones diferentes
3. **Lógica de disponibilidade falha**: Avaliações apareciam como disponíveis antes do horário de aplicação

### Solução Implementada

#### 1. Tratamento de Datas sem Timezone

```python
# Antes (problemático)
application_local = convert_to_local_time(class_test.application)
current_local = current_time
time_diff = current_local - application_local

# Depois (corrigido)
application_dt = class_test.application
if application_dt.tzinfo is None:
    # Se não tem timezone, assumir UTC e converter para local
    application_dt = application_dt.replace(tzinfo=timezone.utc)
application_local = application_dt.astimezone(current_time.tzinfo)
is_available_now = current_time >= application_local
```

#### 2. Lógica de Comparação Corrigida

- **Assunção UTC**: Datas do banco sem timezone são tratadas como UTC
- **Conversão consistente**: Todas as datas são convertidas para o timezone local antes da comparação
- **Comparação direta**: Uso de operadores `>=` e `>` em vez de cálculo de diferença

#### 3. Logs de Debug Adicionados

```python
logging.info(f"Teste {test.id}: current_time={current_time.isoformat()}, application_local={application_local.isoformat()}, is_available_now={is_available_now}")
```

### Rotas Corrigidas

1. **`GET /test/my-class/tests`** - Lista de avaliações do aluno
2. **`GET /test/class/<class_id>/tests/complete`** - Avaliações completas da classe
3. **`POST /test/<test_id>/start-session`** - Iniciar sessão
4. **`POST /student-answers/submit`** - Submeter respostas
5. **`POST /student-answers/save-partial`** - Salvar respostas parciais
6. **`GET /test/<test_id>/session-info`** - Informações da sessão

## Como Funciona Agora

### Detecção Automática de Timezone

1. **Variável de Ambiente TZ**: Se definida, usa este timezone
2. **Timezone do Sistema**: Se TZ não estiver definida, usa o timezone local do sistema
3. **Fallback UTC**: Se não conseguir detectar, usa UTC

### Funções Principais

```python
# Obter tempo atual no timezone local
from app.utils.timezone_utils import get_local_time
current_time = get_local_time()

# Converter datetime para timezone local
from app.utils.timezone_utils import convert_to_local_time
local_time = convert_to_local_time(some_datetime)

# Informações do timezone
from app.utils.timezone_utils import get_timezone_info
tz_info = get_timezone_info()
```

## Compatibilidade

### Funções Mantidas (DEPRECATED)

As seguintes funções foram mantidas para compatibilidade, mas agora usam o timezone local:

- `get_brazil_time()` → `get_local_time()`
- `convert_to_brazil_time()` → `convert_to_local_time()`
- `get_brazil_timezone_info()` → `get_timezone_info()`

### Migração Gradual

O código existente continuará funcionando, mas é recomendado migrar para as novas funções:

```python
# ❌ Antigo (ainda funciona, mas deprecated)
from app.utils.timezone_utils import get_brazil_time
current_time = get_brazil_time()

# ✅ Novo (recomendado)
from app.utils.timezone_utils import get_local_time
current_time = get_local_time()
```

## Configuração do Timezone

### Para Desenvolvimento Local

O servidor automaticamente detectará o timezone do seu sistema.

### Para Produção

1. **Usando Variável de Ambiente**:
   ```bash
   export TZ=America/Sao_Paulo
   python run.py
   ```

2. **No Docker**:
   ```bash
   docker run -e TZ=America/Sao_Paulo your-app
   ```

3. **No Dockerfile**:
   ```dockerfile
   ENV TZ=America/Sao_Paulo
   ```

## Vantagens da Mudança

1. **Consistência**: O servidor sempre usa o timezone local
2. **Flexibilidade**: Funciona em qualquer região sem configuração manual
3. **Simplicidade**: Elimina conversões desnecessárias
4. **Confiabilidade**: Reduz bugs relacionados a timezone
5. **Manutenibilidade**: Código mais limpo e fácil de entender

## Testando as Mudanças

### 1. Verificar Timezone Atual

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:5000/test/debug/timezone
```

### 2. Verificar Disponibilidade de Avaliação

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:5000/test/debug/availability/test-uuid
```

### 3. Aplicar Avaliação

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "classes": [{
         "class_id": "class-uuid",
         "application": "2024-01-15T10:00:00",
         "expiration": "2024-01-15T12:00:00"
       }]
     }' \
     http://localhost:5000/test/test-uuid/apply
```

### 4. Verificar Disponibilidade

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:5000/test/my-class/tests
```

## Troubleshooting

### Problema: Datas incorretas

**Solução**: Verifique o timezone do servidor usando o endpoint de debug:
```bash
curl http://localhost:5000/test/debug/timezone
```

### Problema: Avaliações disponíveis antes do horário

**Solução**: Use o endpoint de debug de disponibilidade:
```bash
curl http://localhost:5000/test/debug/availability/test-uuid
```

### Problema: Inconsistências entre ambientes

**Solução**: Configure a variável de ambiente TZ consistentemente:
```bash
export TZ=America/Sao_Paulo  # Para Brasil
export TZ=UTC                 # Para UTC
```

### Problema: Código antigo não funciona

**Solução**: As funções antigas ainda funcionam, mas migre gradualmente para as novas:
```python
# Substitua gradualmente
get_brazil_time() → get_local_time()
convert_to_brazil_time() → convert_to_local_time()
```

## Próximos Passos

1. **Monitorar**: Acompanhar logs para identificar problemas
2. **Migrar**: Substituir gradualmente funções deprecated
3. **Testar**: Validar em diferentes ambientes
4. **Documentar**: Atualizar documentação da API

## Rollback

Se necessário, é possível reverter as mudanças:

1. Restaurar `timezone_utils.py` para versão anterior
2. Reverter mudanças nas rotas
3. Remover configuração de timezone do Dockerfile

**Nota**: Dados salvos com o novo sistema podem precisar de migração se houver rollback.
