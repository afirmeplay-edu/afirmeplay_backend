# Correção de Timezone nas Competições

## Problema Identificado

Quando um usuário em Maceió/Alagoas (UTC-3) selecionava horários para a competição, o sistema estava marcando incorretamente os status `is_enrollment_open`, `is_application_open` e `is_finished`.

### Exemplo do Problema

**Configuração:**
- Início de inscrição: 10/02/2026 às 10:03
- Fim de inscrição: 10/02/2026 às 10:10
- Horário atual: 10:08 (ainda dentro do período)

**Resultado esperado:** `is_enrollment_open = True`  
**Resultado obtido:** `is_enrollment_open = False` ❌

## Causa Raiz

O problema estava na função `_normalize_datetime_for_comparison()` no arquivo `app/competitions/models/competition.py`.

### Fluxo do Problema

1. **Frontend envia:** `"2026-02-10T10:03:00"` (naive, sem timezone)
   - Usuário pensa: "10:03 no meu horário local (UTC-3)"

2. **Backend salva:** `"2026-02-10 10:03:00"` (naive no banco de dados)
   - Não interpreta como UTC-3, apenas salva como naive

3. **Backend compara:**
   - Horário atual: 10:08 em Maceió = 13:08 UTC
   - Converte para UTC naive: `13:08`
   - Horário do banco (naive): `10:03`
   - Compara: `13:08 > 10:10?` SIM ❌ (errado!)

O backend estava tratando o horário naive do banco como se fosse UTC, quando na verdade deveria ser interpretado como America/Sao_Paulo (UTC-3).

## Solução Implementada

Modificamos a função `_normalize_datetime_for_comparison()` para aceitar um parâmetro `competition_timezone` e interpretar corretamente os horários naive do banco de dados:

```python
def _normalize_datetime_for_comparison(dt, competition_timezone=None):
    """
    Normaliza datetime para comparação consistente em UTC naive.
    
    Args:
        dt: datetime a ser normalizado
        competition_timezone: timezone da competição (ex: 'America/Sao_Paulo')
                            usado para interpretar datetimes naive do banco
    
    Returns:
        datetime naive em UTC para comparação
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        # Se for timezone-aware, converter para UTC e remover timezone
        if dt.tzinfo is not None:
            dt_utc = dt.astimezone(timezone.utc)
            return dt_utc.replace(tzinfo=None)
        # Se for naive (horários do banco), interpretar como timezone da competição
        # antes de converter para UTC
        if competition_timezone:
            try:
                import pytz
                tz = pytz.timezone(competition_timezone)
                # Localizar o datetime naive no timezone da competição
                dt_aware = tz.localize(dt)
                # Converter para UTC e remover timezone
                dt_utc = dt_aware.astimezone(timezone.utc)
                return dt_utc.replace(tzinfo=None)
            except Exception:
                # Se falhar, assumir que já está em UTC
                pass
        # Se não tem timezone da competição ou falhou, assumir que está em UTC
        return dt
    return dt
```

### Mudanças nas Properties

Atualizamos as properties `is_enrollment_open`, `is_application_open` e `is_finished` para passar o timezone da competição:

```python
@property
def is_enrollment_open(self) -> bool:
    """Verifica se está no período de inscrição."""
    now = get_local_time()
    now_naive = _normalize_datetime_for_comparison(now)
    # Interpretar horários do banco como timezone da competição
    start = _normalize_datetime_for_comparison(self.enrollment_start, self.timezone)
    end = _normalize_datetime_for_comparison(self.enrollment_end, self.timezone)
    if start is None or end is None:
        return False
    return start <= now_naive <= end
```

## Resultado da Correção

### Fluxo Correto Agora

1. **Frontend envia:** `"2026-02-10T10:03:00"` (naive)
2. **Backend salva:** `"2026-02-10 10:03:00"` (naive no banco)
3. **Backend compara:**
   - Horário atual: 10:08 em Maceió = 13:08 UTC
   - Converte para UTC naive: `13:08`
   - Horário do banco interpretado como America/Sao_Paulo:
     - `10:03 -03:00` = `13:03 UTC`
     - `10:10 -03:00` = `13:10 UTC`
   - Compara: `13:03 <= 13:08 <= 13:10?` SIM ✅ (correto!)

## Teste de Validação

Executamos um teste simulando às 10:08 no horário local:

```
HORARIOS NO BANCO (naive):
   enrollment_start: 2026-02-10 10:03:00
   enrollment_end: 2026-02-10 10:10:00
   timezone: America/Sao_Paulo

HORARIO SIMULADO AS 10:08:
   Sao Paulo: 2026-02-10 10:08:00-03:00
   UTC: 2026-02-10 13:08:00+00:00

NORMALIZACAO COM A CORRECAO:
   now (UTC naive): 2026-02-10 13:08:00
   start (UTC naive): 2026-02-10 13:03:00
   end (UTC naive): 2026-02-10 13:10:00

VERIFICACAO:
   Esta no periodo de inscricao? True ✅

RESULTADO:
   OK! As 10:08, a inscricao deveria estar aberta - e esta!
```

## Problema Adicional Descoberto: Status 'encerrada' Prematuramente

Após a correção inicial, foi identificado um segundo problema: mesmo com `is_enrollment_open=true` e `is_finished=false` corretos, o campo `status` estava sendo alterado para `'encerrada'` assim que o horário de inscrição iniciava.

### Causa

O sistema possui um **loop em background** que roda a cada 15 minutos (arquivo `app/__init__.py`) e chama `CompetitionRankingService.finalize_all_expired_competitions()`. Esta função estava fazendo comparação direta de horários:

```python
# ANTES (errado)
now = datetime.utcnow()  # 13:45 UTC
competitions = Competition.query.filter(
    Competition.expiration < now,  # Comparando "11:00" naive < "13:45" naive
    Competition.status.in_(['aberta', 'em_andamento']),
).all()
```

O problema: comparava horário naive do banco (que deveria ser interpretado como UTC-3) com UTC atual, finalizando competições prematuramente.

### Solução

Modificamos para usar a property `is_finished` que já interpreta corretamente o timezone:

```python
# DEPOIS (correto)
candidate_competitions = Competition.query.filter(
    Competition.status.in_(['aberta', 'em_andamento']),
).all()

# Filtrar usando is_finished property
competitions = [c for c in candidate_competitions if c.is_finished]
```

## Próximos Passos

1. **Reiniciar o servidor** para aplicar as mudanças
2. **Testar no frontend** criando uma nova competição e verificando os horários
3. **Aguardar 15 minutos** para verificar que o loop em background não finaliza competições incorretamente
4. **Verificar competições existentes** que possam ter sido finalizadas incorretamente pelo bug

## Impacto

Esta correção afeta:

### Modelo Competition (app/competitions/models/competition.py)
- ✅ `_normalize_datetime_for_comparison()` - Agora interpreta datetimes naive no timezone da competição
- ✅ `is_enrollment_open` - Status de inscrição aberta
- ✅ `is_application_open` - Status de aplicação aberta
- ✅ `is_finished` - Status de competição finalizada

### Serviços
- ✅ `CompetitionRankingService.finalize_all_expired_competitions()` - Usa `is_finished` property
- ✅ `CompetitionService.get_available_competitions_for_student()` - Usa properties ao invés de comparações diretas
- ✅ `CompetitionService.enroll_student_in_competition()` - Usa `is_enrollment_open` property
- ✅ `CompetitionService.cancel_enrollment()` - Usa `is_application_open` property

### Rotas
- ✅ `/competitions/<id>/finalize` - Usa `is_finished` property
- ✅ `/competitions/<id>/start` - Usa `is_application_open` property
- ✅ `/competitions/<id>/eligible-students` - Usa `is_enrollment_open` property

## Nota Importante

**Não é necessário alterar o frontend.** O problema estava apenas no backend, na interpretação dos horários naive. O frontend continua enviando os horários corretamente no formato ISO naive, e agora o backend interpreta corretamente esses horários como estando no timezone da competição.
