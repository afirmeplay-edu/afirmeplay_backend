# 🔧 Correção de Problemas de Expiração e Disponibilidade de Avaliações

## 📋 Resumo dos Problemas Identificados

1. **Avaliações permaneciam disponíveis após a data de expiração**
2. **Erro de comparação de datetime: "can't compare offset-naive and offset-aware datetimes"**
3. **Erro de variável: "cannot access local variable 'session' where it is not associated with a value"**
4. **Inconsistência entre rotas: avaliação marcada como expirada em uma rota e disponível em outra**
5. **Problema de fuso horário: datas sendo comparadas em fusos diferentes**

## ✅ Correções Implementadas

### 1. **Verificação de Expiração com Precisão de Tempo**

**Problema:** Avaliações estavam sendo consideradas disponíveis apenas pela data, ignorando a hora.

**Solução:** Adicionada verificação tanto da data de aplicação quanto da data de expiração com precisão de hora e minuto.

**Arquivos modificados:**
- `app/routes/test_routes.py` - Funções: `listar_avaliacoes_minha_classe`, `obter_avaliacoes_completas_classe`, `start_test_session`
- `app/routes/student_answer_routes.py` - Função: `can_student_start_test`

### 2. **Correção de Comparação de Datetime**

**Problema:** Erro "can't compare offset-naive and offset-aware datetimes" ao comparar datas.

**Solução:** Normalização de todas as datas para datetime naive antes da comparação.

```python
# Antes (causava erro)
if current_time > expiration_time:  # Erro se um tem tzinfo e outro não

# Depois (corrigido)
expiration_clean = expiration.replace(tzinfo=None) if expiration.tzinfo else expiration
current_clean = current_time.replace(tzinfo=None) if current_time.tzinfo else current_time
if current_clean > expiration_clean:  # Comparação segura
```

### 3. **Correção de Escopo de Variável**

**Problema:** Erro "cannot access local variable 'session' where it is not associated with a value".

**Solução:** Movida a declaração da variável `session` para fora dos blocos condicionais.

```python
# Antes (causava erro)
if condition:
    session = TestSession.query.filter_by(...).first()
# session pode não estar definida aqui

# Depois (corrigido)
session = TestSession.query.filter_by(...).first()  # Sempre definida
if condition:
    # usar session
```

### 4. **Padronização de Fuso Horário**

**Problema:** Inconsistência entre rotas devido a comparação de datas em fusos horários diferentes.

**Solução:** Padronização para usar o fuso horário do Brasil em todas as comparações.

```python
# Antes (inconsistente)
current_time = datetime.utcnow()  # UTC
# Comparação com datas que podem estar em fuso local

# Depois (consistente)
from app.utils.timezone_utils import get_brazil_time
current_time = get_brazil_time()  # Fuso horário do Brasil
# Todas as comparações no mesmo fuso horário
```

## 🔄 Novos Status de Disponibilidade

Adicionados novos status para melhor controle:

- `"available"` - Avaliação disponível para iniciar
- `"not_started"` - Ainda não chegou a data/hora de aplicação
- `"expired"` - Avaliação expirada
- `"completed"` - Aluno já completou
- `"not_available"` - Status global não permite

## 📊 Exemplo de Cenário Corrigido

**Avaliação:**
- Data de aplicação: `2025-07-20T09:50:00`
- Data de expiração: `2025-07-20T09:57:00`
- Hora atual: `2025-07-20T09:54:00` (horário do Brasil)

**Comportamento:**
- ✅ **09:49:00** - Status: `"not_started"`, `can_start: false`
- ✅ **09:50:00** - Status: `"available"`, `can_start: true`
- ✅ **09:56:00** - Status: `"available"`, `can_start: true`
- ✅ **09:57:00** - Status: `"expired"`, `can_start: false`

## 🧪 Teste de Verificação

Criado arquivo `test_expiration_fix.py` para verificar o comportamento correto:

```bash
python test_expiration_fix.py
```

## 📁 Arquivos Modificados

1. **`app/routes/test_routes.py`**
   - `listar_avaliacoes_minha_classe()` - Verificação de disponibilidade com tempo
   - `obter_avaliacoes_completas_classe()` - Verificação de disponibilidade com tempo
   - `start_test_session()` - Verificação de disponibilidade e expiração

2. **`app/routes/student_answer_routes.py`**
   - `can_student_start_test()` - Verificação completa de permissão

3. **`CORRECAO_EXPIRACAO.md`** - Esta documentação

4. **`test_expiration_fix.py`** - Script de teste

## 🚀 Próximos Passos

1. **Deploy das correções**
2. **Testes de integração** com dados reais
3. **Verificação do frontend** para lidar com os novos status
4. **Monitoramento** do comportamento em produção

## ⚠️ Observações Importantes

- Todas as comparações de data agora usam o fuso horário do Brasil
- As verificações consideram tanto data quanto hora/minuto
- O sistema agora é consistente entre todas as rotas
- Novos status fornecem feedback mais preciso para o frontend 