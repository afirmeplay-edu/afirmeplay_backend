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
page = 1
per_page = 10

print("=== TESTE DA LÓGICA DE PAGINAÇÃO ===")

# 1. Simular a query base que está funcionando
print("1. Construindo query base...")
try:
    query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                               .join(Class, ClassTest.class_id == Class.id)\
                               .join(Grade, Class.grade_id == Grade.id)\
                               .join(School, Class.school_id == School.id)\
                               .join(City, School.city_id == City.id)\
                               .filter(City.id == municipio)\
                               .filter(Test.id == avaliacao)
    
    print(f"   ✅ Query base construída com sucesso")
    
except Exception as e:
    print(f"   ❌ Erro ao construir query base: {str(e)}")
    exit(1)

# 2. Simular filtros de permissões
print("\n2. Aplicando filtros de permissões...")
escola_ids = ['56bfd6b8-8465-4331-a13b-06cb06a8516d']  # Escola onde a avaliação foi aplicada

if escola_ids:
    query_base = query_base.filter(School.id.in_(escola_ids))
    print(f"   ✅ Filtro de escolas aplicado: {len(escola_ids)} escolas")

# 3. Testar a query base
print("\n3. Testando query base...")
try:
    todas_avaliacoes_escopo = query_base.all()
    print(f"   ✅ Query base retorna: {len(todas_avaliacoes_escopo)} avaliações")
    
    if todas_avaliacoes_escopo:
        for ct in todas_avaliacoes_escopo:
            print(f"     - ClassTest ID: {ct.id}, Class: {ct.class_id}, Test: {ct.test_id}")
            
except Exception as e:
    print(f"   ❌ Erro na query base: {str(e)}")
    exit(1)

# 4. Testar paginação
print("\n4. Testando paginação...")
try:
    # Contar total
    total = query_base.count()
    print(f"   ✅ Total de registros: {total}")
    
    # Calcular offset
    offset = (page - 1) * per_page
    print(f"   ✅ Offset calculado: {offset}")
    
    # Aplicar paginação
    class_tests_paginados = query_base.offset(offset).limit(per_page).all()
    print(f"   ✅ Registros paginados: {len(class_tests_paginados)}")
    
    if class_tests_paginados:
        for ct in class_tests_paginados:
            print(f"     - ClassTest ID: {ct.id}, Class: {ct.class_id}, Test: {ct.test_id}")
    
    # Calcular total de páginas
    total_pages = (total + per_page - 1) // per_page
    print(f"   ✅ Total de páginas: {total_pages}")
    
except Exception as e:
    print(f"   ❌ Erro na paginação: {str(e)}")
    import traceback
    traceback.print_exc()

# 5. Verificar se os dados estão sendo processados corretamente
print("\n5. Verificando processamento dos dados...")
if 'class_tests_paginados' in locals() and class_tests_paginados:
    print(f"   ✅ Dados disponíveis para processamento: {len(class_tests_paginados)}")
    
    # Simular o processamento que a rota faz
    resultados_detalhados = []
    for class_test in class_tests_paginados:
        evaluation = class_test.test
        
        # Buscar informações da escola
        escola_nome = "N/A"
        municipio_nome = "N/A"
        estado_nome = "N/A"
        if class_test.class_ and class_test.class_.school:
            escola_nome = class_test.class_.school.name
            if class_test.class_.school.city:
                municipio_nome = class_test.class_.school.city.name
                estado_nome = class_test.class_.school.city.state
        
        result = {
            "id": evaluation.id,
            "titulo": evaluation.title,
            "escola": escola_nome,
            "municipio": municipio_nome,
            "estado": estado_nome
        }
        
        resultados_detalhados.append(result)
        print(f"     - Processado: {evaluation.title} -> {escola_nome}")
    
    print(f"   ✅ Total de resultados processados: {len(resultados_detalhados)}")
else:
    print(f"   ❌ Nenhum dado disponível para processamento")

print("\n=== FIM DO TESTE ===")
