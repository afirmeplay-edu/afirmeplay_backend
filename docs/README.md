# Documentação Técnica - InnovaPlay Backend

## 📚 Índice de Documentação

### Correções e Soluções

1. **[Correção: Erro de Tipo UUID vs VARCHAR](./CORRECAO_UUID_VARCHAR_TIPO_MISMATCH.md)** ⭐ **PRINCIPAL**
   - Problema: `operator does not exist: character varying = uuid`
   - Solução: Correções em models, queries, helpers e relationships
   - Cobre: Todos os erros relacionados a incompatibilidade UUID/VARCHAR
   - Última atualização: 2026-01-07

2. **[Correção: Class.school como Property vs Relationship](./CORRECAO_CLASS_SCHOOL_PROPERTY.md)**
   - Problema: `ArgumentError: expected ORM mapped attribute for loader strategy argument`
   - Solução: Remover `joinedload(Class.school)` de queries
   - Relacionado: Parte da solução do problema UUID vs VARCHAR
   - Última atualização: 2026-01-07

---

## 🔍 Como Usar Esta Documentação

### Quando encontrar o erro principal:
```
operator does not exist: character varying = uuid
```

**Consulte:** [CORRECAO_UUID_VARCHAR_TIPO_MISMATCH.md](./CORRECAO_UUID_VARCHAR_TIPO_MISMATCH.md)

Este documento cobre:
- ✅ Correção de models (UUID → String)
- ✅ Correção de `School.query.get()`
- ✅ Correção de `ClassTest.query.filter_by(test_id=)`
- ✅ Correção de JSONB
- ✅ Correção de query filters
- ✅ Correção de dashboard_service
- ✅ Correção de Class.school (property vs relationship)

### Quando encontrar erro com joinedload:
```
ArgumentError: expected ORM mapped attribute for loader strategy argument
```

**Consulte:** [CORRECAO_CLASS_SCHOOL_PROPERTY.md](./CORRECAO_CLASS_SCHOOL_PROPERTY.md)

---

## 📝 Adicionar Nova Documentação

Para adicionar nova documentação:

1. Crie um arquivo `.md` na pasta `docs/`
2. Use o formato: `CORRECAO_[NOME_DO_PROBLEMA].md`
3. Adicione uma entrada neste README
4. Inclua exemplos de código, antes/depois, e como testar

---

**Última atualização**: 2026-01-07

