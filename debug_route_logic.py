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

print("=== DEBUG DA LÓGICA DA ROTA ===")
print(f"Estado: {estado}")
print(f"Município: {municipio}")
print(f"Avaliação: {avaliacao}")
print(f"Escola: {escola}")
print(f"Série: {serie}")
print(f"Turma: {turma}")

# 1. Verificar se o município existe
city = City.query.get(municipio)
if not city:
    print("❌ Município não encontrado")
    exit(1)

print(f"\n✅ Município encontrado: {city.name} ({city.id})")
print(f"  - Estado: {city.state}")

# 2. Verificar se a avaliação existe
test = Test.query.get(avaliacao)
if not test:
    print("❌ Avaliação não encontrada")
    exit(1)

print(f"\n✅ Avaliação encontrada: {test.title} ({test.id})")
print(f"  - Status: {test.status}")

# 3. Verificar onde a avaliação foi aplicada
class_tests = ClassTest.query.filter_by(test_id=avaliacao).all()
if not class_tests:
    print("❌ Avaliação não foi aplicada em nenhuma turma")
    exit(1)

print(f"\n✅ Avaliação aplicada em {len(class_tests)} turma(s)")
class_ids = [ct.class_id for ct in class_tests]

# 4. Verificar as turmas e escolas
classes = Class.query.filter(Class.id.in_(class_ids)).all()
escolas_avaliacao = []
for classe in classes:
    school = School.query.get(classe.school_id)
    if school:
        escolas_avaliacao.append(school)
        print(f"  - Turma: {classe.name or 'N/A'} -> Escola: {school.name} -> Município: {school.city.name if school.city else 'N/A'}")

# 5. Verificar se as escolas pertencem ao município
escolas_filtradas = []
for escola_obj in escolas_avaliacao:
    if escola_obj.city_id == municipio:
        escolas_filtradas.append(escola_obj)
        print(f"  ✅ Escola {escola_obj.name} pertence ao município {city.name}")
    else:
        print(f"  ❌ Escola {escola_obj.name} NÃO pertence ao município {city.name}")

print(f"\n📊 Resumo:")
print(f"  - Total de escolas onde avaliação foi aplicada: {len(escolas_avaliacao)}")
print(f"  - Escolas no município correto: {len(escolas_filtradas)}")

# 6. Verificar se há alunos e resultados
if escolas_filtradas:
    # Buscar alunos das turmas
    students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    print(f"\n👥 Alunos nas turmas: {len(students)}")
    
    # Buscar resultados calculados
    results = EvaluationResult.query.filter_by(test_id=avaliacao).all()
    print(f"📊 Resultados calculados: {len(results)}")
    
    if results:
        for result in results:
            student = Student.query.get(result.student_id)
            print(f"  - {student.name if student else 'N/A'}: Nota {result.grade}, Proficiência {result.proficiency}")
    
    # Verificar se a query base retornaria dados
    print(f"\n🔍 Testando query base...")
    try:
        query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                   .join(Class, ClassTest.class_id == Class.id)\
                                   .join(Grade, Class.grade_id == Grade.id)\
                                   .join(School, Class.school_id == School.id)\
                                   .join(City, School.city_id == City.id)\
                                   .filter(City.id == municipio)\
                                   .filter(Test.id == avaliacao)
        
        # Aplicar filtro por escolas
        school_ids = [e.id for e in escolas_filtradas]
        if school_ids:
            query_base = query_base.filter(School.id.in_(school_ids))
        
        # Executar query
        todas_avaliacoes_escopo = query_base.all()
        print(f"  ✅ Query executada com sucesso: {len(todas_avaliacoes_escopo)} avaliações encontradas")
        
        if todas_avaliacoes_escopo:
            for ct in todas_avaliacoes_escopo:
                print(f"    - ClassTest ID: {ct.id}, Class: {ct.class_id}, Test: {ct.test_id}")
        
    except Exception as e:
        print(f"  ❌ Erro na query: {str(e)}")

else:
    print(f"\n❌ Nenhuma escola encontrada no município correto")

print("\n=== FIM DO DEBUG ===")
