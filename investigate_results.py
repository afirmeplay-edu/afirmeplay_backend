#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app import create_app, db
from app.models.studentAnswer import StudentAnswer
from app.models.test import Test
from app.models.evaluationResult import EvaluationResult
from app.models.classTest import ClassTest
from app.models.student import Student

app = create_app()
app.app_context().push()

test_id = '31ad4ada-6f68-406e-95ff-0ee1bbf26d8a'

print("=== INVESTIGAÇÃO DE RESULTADOS ===")
print(f"Teste ID: {test_id}")

# 1. Verificar se o teste existe
test = Test.query.get(test_id)
if test:
    print(f"\n✅ Teste encontrado:")
    print(f"  - Título: {test.title}")
    print(f"  - Status: {test.status}")
    print(f"  - Total de questões: {len(test.questions) if test.questions else 0}")
else:
    print(f"\n❌ Teste não encontrado")
    exit(1)

# 2. Verificar respostas dos alunos
answers = StudentAnswer.query.filter_by(test_id=test_id).all()
print(f"\n📝 Respostas dos alunos:")
print(f"  - Total de respostas: {len(answers)}")

if answers:
    for i, answer in enumerate(answers[:5]):  # Mostrar apenas as primeiras 5
        print(f"    {i+1}. Student: {answer.student_id}, Question: {answer.question_id}, Answer: {answer.answer}")

# 3. Verificar se há resultados calculados
results = EvaluationResult.query.filter_by(test_id=test_id).all()
print(f"\n📊 Resultados calculados:")
print(f"  - Total de resultados: {len(results)}")

if results:
    for result in results:
        print(f"    - Student: {result.student_id}, Grade: {result.grade}, Proficiency: {result.proficiency}, Classification: {result.classification}")

# 4. Verificar turmas onde o teste foi aplicado
class_tests = ClassTest.query.filter_by(test_id=test_id).all()
print(f"\n🏫 Turmas onde o teste foi aplicado:")
print(f"  - Total de turmas: {len(class_tests)}")

if class_tests:
    for ct in class_tests:
        print(f"    - Class ID: {ct.class_id}, Status: {ct.status}")

# 5. Verificar alunos das turmas
if class_tests:
    class_ids = [ct.class_id for ct in class_tests]
    students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    print(f"\n👥 Alunos das turmas:")
    print(f"  - Total de alunos: {len(students)}")
    
    if students:
        for student in students[:5]:  # Mostrar apenas os primeiros 5
            print(f"    - ID: {student.id}, Nome: {student.name}, Class: {student.class_id}")

# 6. Verificar se há respostas para cada aluno
print(f"\n🔍 Verificando respostas por aluno:")
if class_tests:
    class_ids = [ct.class_id for ct in class_tests]
    students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    
    for student in students:
        student_answers = StudentAnswer.query.filter_by(
            test_id=test_id,
            student_id=student.id
        ).all()
        print(f"  - {student.name} (ID: {student.id}): {len(student_answers)} respostas")

print("\n=== FIM DA INVESTIGAÇÃO ===")
