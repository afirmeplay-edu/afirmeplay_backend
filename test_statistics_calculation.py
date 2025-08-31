#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models.city import City
from app.models.school import School
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.test import Test
from app.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.models.grades import Grade

app = create_app()
app.app_context().push()

# Parâmetros da requisição
estado = "Rondônia"
municipio = "9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d"
avaliacao = "31ad4ada-6f68-406e-95ff-0ee1bbf26d8a"
escola = "all"
serie = "all"
turma = "all"

print("=== TESTE DO CÁLCULO DE ESTATÍSTICAS ===")

# 1. Simular a query base que está funcionando
print("1. Testando query base...")
try:
    query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                               .join(Class, ClassTest.class_id == Class.id)\
                               .join(Grade, Class.grade_id == Grade.id)\
                               .join(School, Class.school_id == School.id)\
                               .join(City, School.city_id == City.id)\
                               .filter(City.id == municipio)\
                               .filter(Test.id == avaliacao)
    
    todas_avaliacoes_escopo = query_base.all()
    print(f"   ✅ Query base retorna: {len(todas_avaliacoes_escopo)} avaliações")
    
    if todas_avaliacoes_escopo:
        for ct in todas_avaliacoes_escopo:
            print(f"     - ClassTest ID: {ct.id}, Class: {ct.class_id}, Test: {ct.test_id}")
            
except Exception as e:
    print(f"   ❌ Erro na query base: {str(e)}")
    exit(1)

# 2. Simular o escopo de busca
print("\n2. Simulando escopo de busca...")
scope_info = {
    'municipio_id': municipio,
    'city_data': City.query.get(municipio),
    'escolas': [School.query.get('56bfd6b8-8465-4331-a13b-06cb06a8516d')],
    'estado': estado,
    'municipio': municipio,
    'escola': escola,
    'serie': serie,
    'turma': turma,
    'avaliacao': avaliacao
}

print(f"   Scope info: {scope_info}")

# 3. Determinar nível de granularidade
print("\n3. Determinando nível de granularidade...")
nivel_granularidade = "avaliacao"  # Porque temos uma avaliação específica
print(f"   Nível de granularidade: {nivel_granularidade}")

# 4. Simular a função _calcular_estatisticas_consolidadas_por_escopo
print("\n4. Simulando cálculo de estatísticas...")
try:
    # Coletar dados do escopo
    test_ids = [ct.test_id for ct in todas_avaliacoes_escopo]
    class_ids = [ct.class_id for ct in todas_avaliacoes_escopo]
    print(f"   test_ids: {test_ids}")
    print(f"   class_ids: {class_ids}")
    
    # Buscar alunos baseado no escopo
    if nivel_granularidade == "avaliacao":
        # Para avaliação específica, contar apenas alunos das turmas onde foi aplicada
        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        print(f"   ✅ Avaliação específica: total_alunos={total_alunos}")
    else:
        # Para outros níveis, buscar todos os alunos do escopo
        print(f"   ⚠️ Outro nível: {nivel_granularidade}")
        todos_alunos = []
        total_alunos = 0
    
    # Buscar resultados das avaliações do escopo
    resultados_escopo = EvaluationResult.query.filter(EvaluationResult.test_id.in_(test_ids)).all()
    alunos_participantes = len(resultados_escopo)
    print(f"   ✅ resultados_escopo: {alunos_participantes}")
    
    # Calcular estatísticas consolidadas
    if resultados_escopo:
        media_nota = sum(r.grade for r in resultados_escopo) / len(resultados_escopo)
        media_proficiencia = sum(r.proficiency for r in resultados_escopo) / len(resultados_escopo)
        print(f"   ✅ Médias calculadas: nota={media_nota}, proficiência={media_proficiencia}")
    else:
        media_nota = 0.0
        media_proficiencia = 0.0
        print(f"   ⚠️ Nenhum resultado encontrado")
    
    # Calcular distribuição consolidada
    distribuicao_geral = {
        'abaixo_do_basico': 0,
        'basico': 0,
        'adequado': 0,
        'avancado': 0
    }
    
    for resultado in resultados_escopo:
        classificacao = resultado.classification.lower()
        if 'abaixo' in classificacao or 'básico' in classificacao:
            distribuicao_geral['abaixo_do_basico'] += 1
        elif 'básico' in classificacao or 'basico' in classificacao:
            distribuicao_geral['basico'] += 1
        elif 'adequado' in classificacao:
            distribuicao_geral['adequado'] += 1
        elif 'avançado' in classificacao or 'avancado' in classificacao:
            distribuicao_geral['avancado'] += 1
    
    print(f"   ✅ Distribuição calculada: {distribuicao_geral}")
    
    # Calcular alunos ausentes
    alunos_ausentes = total_alunos - alunos_participantes
    print(f"   ✅ Cálculo final: total_alunos={total_alunos}, alunos_participantes={alunos_participantes}, alunos_ausentes={alunos_ausentes}")
    
    # Retornar estatísticas
    estatisticas = {
        "tipo": nivel_granularidade,
        "nome": "Avaliação Específica",
        "estado": scope_info.get('estado', 'Todos os estados'),
        "municipio": scope_info.get('city_data').name if scope_info.get('city_data') else "Todos os municípios",
        "escola": None,
        "serie": None,
        "total_escolas": len(set(ct.class_.school.id for ct in todas_avaliacoes_escopo if ct.class_ and ct.class_.school)),
        "total_series": len(set(ct.class_.grade.id for ct in todas_avaliacoes_escopo if ct.class_ and ct.class_.grade)),
        "total_turmas": len(set(ct.class_id for ct in todas_avaliacoes_escopo)),
        "total_avaliacoes": len(test_ids),
        "total_alunos": total_alunos,
        "alunos_participantes": alunos_participantes,
        "alunos_pendentes": 0,
        "alunos_ausentes": alunos_ausentes,
        "media_nota_geral": round(media_nota, 2),
        "media_proficiencia_geral": round(media_proficiencia, 2),
        "distribuicao_classificacao_geral": distribuicao_geral
    }
    
    print(f"\n✅ ESTATÍSTICAS CALCULADAS COM SUCESSO:")
    print(f"   - Total de escolas: {estatisticas['total_escolas']}")
    print(f"   - Total de turmas: {estatisticas['total_turmas']}")
    print(f"   - Total de avaliações: {estatisticas['total_avaliacoes']}")
    print(f"   - Total de alunos: {estatisticas['total_alunos']}")
    print(f"   - Alunos participantes: {estatisticas['alunos_participantes']}")
    print(f"   - Média nota geral: {estatisticas['media_nota_geral']}")
    print(f"   - Média proficiência geral: {estatisticas['media_proficiencia_geral']}")
    print(f"   - Distribuição: {estatisticas['distribuicao_classificacao_geral']}")
    
except Exception as e:
    print(f"   ❌ Erro no cálculo de estatísticas: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIM DO TESTE ===")
