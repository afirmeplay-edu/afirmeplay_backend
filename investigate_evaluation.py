#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para investigar dados de avaliação no banco
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from app import create_app, db
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.subject import Subject
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from sqlalchemy import text
import json

# Configurações
EVALUATION_ID = "00e2ef94-cc5e-4a53-b06a-38d532e6a6d4"
CITY_ID = "0f93f076-c274-4515-98df-302bbf7e9b15"

app = create_app()

with app.app_context():
    # Definir schema correto
    schema_name = city_id_to_schema_name(CITY_ID)
    set_search_path(schema_name)
    
    print("=" * 80)
    print(f"Investigando Avaliação: {EVALUATION_ID}")
    print(f"City ID: {CITY_ID}")
    print(f"Schema: {schema_name}")
    print("=" * 80)
    
    # Buscar avaliação
    test = Test.query.get(EVALUATION_ID)
    if not test:
        print("❌ Avaliação não encontrada!")
        sys.exit(1)
    
    print(f"\n📋 Avaliação: {test.title}")
    print(f"   Curso: {test.course}")
    print(f"   Subjects Info: {test.subjects_info}")
    
    # Buscar resultados
    results = EvaluationResult.query.filter_by(test_id=EVALUATION_ID).all()
    
    print(f"\n👥 Total de Resultados: {len(results)}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        student = Student.query.get(result.student_id)
        student_name = student.name if student else "Desconhecido"
        
        print(f"\n[{i}] Aluno: {student_name} (ID: {result.student_id})")
        print(f"    Nota Geral: {result.grade}")
        print(f"    Proficiência Geral: {result.proficiency}")
        print(f"    Classificação Geral: {result.classification}")
        print(f"    Acertos: {result.correct_answers}/{result.total_questions}")
        
        # Verificar subject_results
        if result.subject_results:
            print(f"\n    📊 Resultados por Disciplina:")
            for subject_id, subject_data in result.subject_results.items():
                print(f"       - {subject_data.get('subject_name', subject_id)}:")
                print(f"         Nota: {subject_data.get('grade')}")
                print(f"         Proficiência: {subject_data.get('proficiency')}")
                print(f"         Classificação: {subject_data.get('classification')}")
                print(f"         Acertos: {subject_data.get('correct_answers')}/{subject_data.get('answered_questions')}")
        else:
            print(f"    ⚠️  Sem resultados por disciplina no JSON")
    
    # Buscar questões da avaliação
    print("\n" + "=" * 80)
    print("📝 Questões da Avaliação:")
    print("=" * 80)
    
    test_questions = TestQuestion.query.filter_by(test_id=EVALUATION_ID).order_by(TestQuestion.order).all()
    
    questions_by_subject = {}
    for tq in test_questions:
        question = Question.query.get(tq.question_id)
        if question and question.subject_id:
            subject = Subject.query.get(question.subject_id)
            subject_name = subject.name if subject else "Sem disciplina"
            
            if subject_name not in questions_by_subject:
                questions_by_subject[subject_name] = []
            questions_by_subject[subject_name].append(question)
    
    for subject_name, questions in questions_by_subject.items():
        print(f"\n{subject_name}: {len(questions)} questões")
    
    # Buscar respostas do aluno
    if results:
        print("\n" + "=" * 80)
        print("📝 Respostas do Aluno:")
        print("=" * 80)
        
        for result in results:
            student = Student.query.get(result.student_id)
            student_name = student.name if student else "Desconhecido"
            
            print(f"\nAluno: {student_name}")
            
            answers = StudentAnswer.query.filter_by(
                test_id=EVALUATION_ID,
                student_id=result.student_id
            ).all()
            
            answers_by_subject = {}
            for answer in answers:
                question = Question.query.get(answer.question_id)
                if question and question.subject_id:
                    subject = Subject.query.get(question.subject_id)
                    subject_name = subject.name if subject else "Sem disciplina"
                    
                    if subject_name not in answers_by_subject:
                        answers_by_subject[subject_name] = {
                            'total': 0,
                            'correct': 0,
                            'incorrect': 0
                        }
                    
                    answers_by_subject[subject_name]['total'] += 1
                    
                    # Verificar se está correto
                    if question.question_type == 'multiple_choice':
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                    else:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                    
                    if is_correct:
                        answers_by_subject[subject_name]['correct'] += 1
                    else:
                        answers_by_subject[subject_name]['incorrect'] += 1
            
            for subject_name, stats in answers_by_subject.items():
                print(f"\n  {subject_name}:")
                print(f"    Total respondidas: {stats['total']}")
                print(f"    Acertos: {stats['correct']}")
                print(f"    Erros: {stats['incorrect']}")
                print(f"    Percentual: {(stats['correct']/stats['total']*100):.2f}%")
    
    print("\n" + "=" * 80)
    print("✅ Investigação concluída!")
    print("=" * 80)
