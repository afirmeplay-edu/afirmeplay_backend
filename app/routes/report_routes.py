# -*- coding: utf-8 -*-
"""
Rotas especializadas para relatórios de avaliações
Endpoint para geração de relatórios completos com estatísticas detalhadas
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.question import Question
from app.models.subject import Subject
from app.models.school import School
from app.models.city import City
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app import db
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import func, case, desc
from datetime import datetime
from sqlalchemy.orm import joinedload
from collections import defaultdict

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/test', methods=['GET'])
def test_endpoint():
    """Endpoint de teste para verificar se o blueprint está funcionando"""
    return jsonify({
        "message": "Blueprint de relatórios funcionando corretamente",
        "status": "success"
    }), 200


@bp.route('/test-questions/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def test_questions(evaluation_id: str):
    """Endpoint para testar diretamente a propriedade questions"""
    try:
        from app.models.testQuestion import TestQuestion
        from app.models.question import Question
        
        # Teste 1: Query direta na tabela test_questions
        test_questions_direct = TestQuestion.query.filter_by(test_id=evaluation_id).order_by(TestQuestion.order).all()
        
        # Teste 2: IDs das questões
        question_ids = [tq.question_id for tq in test_questions_direct]
        
        # Teste 3: Buscar questões diretamente
        questions_direct = Question.query.filter(Question.id.in_(question_ids)).all()
        
        # Teste 4: Usar a propriedade questions do modelo Test
        test = Test.query.get(evaluation_id)
        questions_property = test.questions if test else []
        
        # Teste 5: Verificar se a questão de Português está na tabela
        portugues_question = TestQuestion.query.filter_by(
            test_id=evaluation_id,
            question_id="4e3305a0-7221-4012-a7aa-8f958b755823"
        ).first()
        
        debug_info = {
            "avaliacao_id": evaluation_id,
            "test_questions_direct": {
                "total": len(test_questions_direct),
                "registros": [
                    {
                        "id": tq.id,
                        "test_id": tq.test_id,
                        "question_id": tq.question_id,
                        "order": tq.order
                    } for tq in test_questions_direct
                ]
            },
            "question_ids": question_ids,
            "questions_direct": {
                "total": len(questions_direct),
                "questoes": [
                    {
                        "id": q.id,
                        "skill": q.skill,
                        "number": q.number
                    } for q in questions_direct
                ]
            },
            "questions_property": {
                "total": len(questions_property),
                "questoes": [
                    {
                        "id": q.id,
                        "skill": q.skill,
                        "number": q.number
                    } for q in questions_property
                ]
            },
            "questao_portugues_teste": {
                "encontrada": portugues_question is not None,
                "dados": {
                    "id": portugues_question.id,
                    "test_id": portugues_question.test_id,
                    "question_id": portugues_question.question_id,
                    "order": portugues_question.order
                } if portugues_question else None
            }
        }
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro ao testar questions: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/debug-disciplinas/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def debug_disciplinas(evaluation_id: str):
    """Endpoint para debug da identificação de disciplinas"""
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter disciplinas usando a função melhorada
        disciplinas = _obter_disciplinas_avaliacao(test)
        
        # Debug detalhado
        debug_info = {
            "avaliacao_id": evaluation_id,
            "titulo": test.title,
            "disciplinas_identificadas": disciplinas,
            "debug_details": {
                "subject_rel": test.subject_rel.name if test.subject_rel else None,
                "subjects_info": test.subjects_info,
                "total_questoes": len(test.questions) if test.questions else 0,
                "questoes_com_habilidades": 0,
                "habilidades_unicas": set(),
                "disciplinas_por_habilidade": {}
            },
            "mapeamento_questoes": {},
            "respostas_por_questao": {},
            "questao_portugues_debug": {}
        }
        
        if test.questions:
            from app.models.skill import Skill
            
            skill_ids = set()
            for question in test.questions:
                if question.skill and question.skill.strip() and question.skill != '{}':
                    clean_skill_id = question.skill.replace('{', '').replace('}', '')
                    skill_ids.add(clean_skill_id)
                    debug_info["debug_details"]["questoes_com_habilidades"] += 1
            
            debug_info["debug_details"]["habilidades_unicas"] = list(skill_ids)
            
            if skill_ids:
                skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
                skills_dict = {str(skill.id): skill for skill in skills}
                
                for skill in skills:
                    subject = Subject.query.get(skill.subject_id) if skill.subject_id else None
                    debug_info["debug_details"]["disciplinas_por_habilidade"][str(skill.id)] = {
                        "skill_code": skill.code,
                        "skill_description": skill.description,
                        "subject_id": skill.subject_id,
                        "subject_name": subject.name if subject else None
                    }
                
                # Mapear questões para disciplinas (mesmo processo das funções de cálculo)
                for question in test.questions:
                    # Questões com skill: mapear via skill.subject_id
                    if question.skill and question.skill.strip() and question.skill != '{}':
                        clean_skill_id = question.skill.replace('{', '').replace('}', '')
                        skill_obj = skills_dict.get(clean_skill_id)
                        
                        disciplina_mapeada = "Não mapeada"
                        if skill_obj and skill_obj.subject_id:
                            subject = Subject.query.get(skill_obj.subject_id)
                            if subject:
                                disciplina_mapeada = subject.name
                            else:
                                disciplina_mapeada = "Disciplina Geral (subject não encontrado)"
                        else:
                            disciplina_mapeada = "Disciplina Geral (skill sem subject_id)"
                        
                        debug_info["mapeamento_questoes"][question.id] = {
                            "numero": question.number,
                            "skill_id": clean_skill_id,
                            "skill_encontrada": skill_obj is not None,
                            "disciplina_mapeada": disciplina_mapeada
                        }
                    else:
                        # Questões sem skill: mapear para disciplina principal da avaliação
                        if test.subject_rel:
                            disciplina_mapeada = test.subject_rel.name
                            debug_info["mapeamento_questoes"][question.id] = {
                                "numero": question.number,
                                "skill_id": "Sem skill",
                                "skill_encontrada": False,
                                "disciplina_mapeada": disciplina_mapeada
                            }
                        else:
                            disciplina_mapeada = "Disciplina Geral"
                            debug_info["mapeamento_questoes"][question.id] = {
                                "numero": question.number,
                                "skill_id": "Sem skill",
                                "skill_encontrada": False,
                                "disciplina_mapeada": disciplina_mapeada
                            }
                    
                    # Verificar respostas para esta questão
                    respostas = StudentAnswer.query.filter_by(
                        test_id=evaluation_id, 
                        question_id=question.id
                    ).count()
                    
                    debug_info["respostas_por_questao"][question.id] = respostas
                    
                    # Debug específico para a questão de Português que sabemos que existe
                    if question.id == "4e3305a0-7221-4012-a7aa-8f958b755823":
                        if question.skill and question.skill.strip() and question.skill != '{}':
                            clean_skill_id = question.skill.replace('{', '').replace('}', '')
                            skill_obj = skills_dict.get(clean_skill_id)
                            debug_info["questao_portugues_debug"] = {
                                "questao_id": question.id,
                                "numero": question.number,
                                "skill_raw": question.skill,
                                "skill_clean": clean_skill_id,
                                "skill_encontrada": skill_obj is not None,
                                "skill_code": skill_obj.code if skill_obj else None,
                                "skill_subject_id": skill_obj.subject_id if skill_obj else None,
                                "disciplina_final": disciplina_mapeada,
                                "total_respostas": respostas
                            }
                        else:
                            debug_info["questao_portugues_debug"] = {
                                "questao_id": question.id,
                                "numero": question.number,
                                "skill_raw": question.skill,
                                "skill_clean": "Sem skill",
                                "skill_encontrada": False,
                                "skill_code": None,
                                "skill_subject_id": None,
                                "disciplina_final": disciplina_mapeada,
                                "total_respostas": respostas
                            }
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro ao debug disciplinas: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/relatorio-completo/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def relatorio_completo(evaluation_id: str):
    """
    Gera relatório completo de uma avaliação com todos os dados solicitados
    
    Args:
        evaluation_id: ID da avaliação
    
    Returns:
        JSON com relatório completo contendo:
        - Total de alunos que realizaram a avaliação
        - Níveis de Aprendizagem por turma
        - Proficiência
        - Nota Geral por turma
        - Acertos por habilidade
    """
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test)
        }
        
        logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
        
        # 2. Níveis de Aprendizagem por turma
        niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
        logging.info(f"Níveis de aprendizagem calculados para disciplinas: {list(niveis_aprendizagem.keys())}")
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
        logging.info(f"Proficiência calculada para disciplinas: {list(proficiencia.get('por_disciplina', {}).keys())}")
        
        # 4. Nota Geral por turma
        nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
        logging.info(f"Nota geral calculada para disciplinas: {list(nota_geral.get('por_disciplina', {}).keys())}")
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
        logging.info(f"Acertos por habilidade calculados para disciplinas: {list(acertos_habilidade.keys())}")
        
        return jsonify({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório completo: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500





def _obter_disciplinas_avaliacao(test: Test) -> List[str]:
    """Obtém as disciplinas da avaliação"""
    disciplinas = []
    
    logging.info(f"Identificando disciplinas para avaliação {test.id}")
    
    # Se a avaliação tem uma disciplina específica
    if test.subject_rel:
        disciplinas.append(test.subject_rel.name)
        logging.info(f"Disciplina encontrada via subject_rel: {test.subject_rel.name}")
    
    # Se tem informações de disciplinas no JSON
    if test.subjects_info and isinstance(test.subjects_info, dict):
        disciplinas.extend(test.subjects_info.keys())
        logging.info(f"Disciplinas encontradas via subjects_info: {list(test.subjects_info.keys())}")
    
    # Buscar disciplinas através das habilidades das questões
    if test.questions:
        from app.models.skill import Skill
        
        skill_ids = set()
        for question in test.questions:
            if question.skill and question.skill.strip() and question.skill != '{}':
                clean_skill_id = question.skill.replace('{', '').replace('}', '')
                skill_ids.add(clean_skill_id)
        
        logging.info(f"Skill IDs encontrados nas questões: {skill_ids}")
        
        if skill_ids:
            skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
            logging.info(f"Habilidades encontradas na tabela Skill: {len(skills)}")
            
            for skill in skills:
                if skill.subject_id:
                    subject = Subject.query.get(skill.subject_id)
                    if subject and subject.name not in disciplinas:
                        disciplinas.append(subject.name)
                        logging.info(f"Disciplina encontrada via habilidade {skill.code}: {subject.name}")
                else:
                    logging.warning(f"Habilidade {skill.code} não tem subject_id")
    
    # Se não encontrou disciplinas, usar padrão
    if not disciplinas:
        disciplinas = ["Disciplina Geral"]
        logging.warning("Nenhuma disciplina encontrada, usando padrão: Disciplina Geral")
    
    disciplinas_finais = list(set(disciplinas))  # Remove duplicatas
    logging.info(f"Disciplinas finais identificadas: {disciplinas_finais}")
    
    return disciplinas_finais


def _calcular_totais_alunos(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula totais de alunos por turma e geral"""
    class_ids = [ct.class_id for ct in class_tests]
    
    # Buscar todos os alunos das turmas onde a avaliação foi aplicada
    students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id.in_(class_ids)).all()
    
    # Buscar resultados da avaliação (alunos que realizaram)
    evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
    results_by_student = {er.student_id: er for er in evaluation_results}
    
    # Agrupar alunos por turma
    students_by_class = defaultdict(list)
    for student in students:
        students_by_class[student.class_id].append(student)
    
    # Calcular estatísticas por turma
    por_turma = []
    total_matriculados = 0
    total_avaliados = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_students = students_by_class[class_id]
        
        # Matriculados = Alunos da turma onde a avaliação foi aplicada
        matriculados = len(class_students)
        # Avaliados = Alunos que realmente realizaram a avaliação (têm resultado)
        avaliados = sum(1 for s in class_students if s.id in results_by_student)
        percentual = (avaliados / matriculados * 100) if matriculados > 0 else 0
        # Faltosos = Matriculados que não realizaram
        faltosos = matriculados - avaliados
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_students and class_students[0].class_:
            turma_nome = class_students[0].class_.name
        
        por_turma.append({
            "turma": turma_nome,
            "matriculados": matriculados,
            "avaliados": avaliados,
            "percentual": round(percentual, 1),
            "faltosos": faltosos
        })
        
        total_matriculados += matriculados
        total_avaliados += avaliados
    
    # Calcular totais gerais
    total_percentual = (total_avaliados / total_matriculados * 100) if total_matriculados > 0 else 0
    total_faltosos = total_matriculados - total_avaliados
    
    return {
        "por_turma": por_turma,
        "total_geral": {
            "matriculados": total_matriculados,
            "avaliados": total_avaliados,
            "percentual": round(total_percentual, 1),
            "faltosos": total_faltosos
        }
    }


def _calcular_niveis_aprendizagem(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula níveis de aprendizagem por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    logging.info(f"Calculando níveis de aprendizagem para avaliação {evaluation_id}")
    logging.info(f"Total de questões: {len(test.questions)}")
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    logging.info(f"Skill IDs encontrados: {skill_ids}")
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
        logging.info(f"Habilidades encontradas na tabela Skill: {len(skills_dict)}")
        
        for skill in skills:
            logging.info(f"Skill: {skill.id} -> {skill.code} -> subject_id: {skill.subject_id}")
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    disciplinas_identificadas = set()
    
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                    disciplinas_identificadas.add(subject.name)
                    logging.info(f"Questão {question.id} mapeada para disciplina via skill: {subject.name}")
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
                    disciplinas_identificadas.add("Disciplina Geral")
                    logging.warning(f"Subject não encontrado para skill {skill_obj.id}")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
                if skill_obj:
                    logging.warning(f"Skill {skill_obj.id} não tem subject_id")
                else:
                    logging.warning(f"Skill não encontrado para ID: {clean_skill_id}")
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
                logging.info(f"Questão {question.id} sem skill mapeada para disciplina principal: {test.subject_rel.name}")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
                logging.warning(f"Questão {question.id} sem skill e avaliação sem disciplina principal")
        

    
    logging.info(f"Disciplinas identificadas nas questões: {disciplinas_identificadas}")
    logging.info(f"Questões mapeadas para disciplinas: {len(question_disciplines)}")
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    logging.info(f"Total de respostas de alunos: {len(student_answers)}")
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    logging.info(f"Alunos com respostas por disciplina: {len(student_discipline_results)}")
    
    # Buscar resultados da avaliação para obter classificações
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    logging.info(f"Total de resultados de avaliação: {len(evaluation_results)}")
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    logging.info(f"Turmas com resultados: {list(results_by_class.keys())}")
    
    # Calcular por turma e disciplina
    disciplinas_resultado = defaultdict(lambda: {
        "por_turma": [],
        "geral": {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0}
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(lambda: {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0})
    dados_gerais_total = {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0}
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        logging.info(f"Processando turma: {turma_nome}")
        
        # Para cada disciplina, calcular níveis de aprendizagem
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        logging.info(f"Disciplinas encontradas na turma {turma_nome}: {disciplinas_turma}")
        
        for disciplina in disciplinas_turma:
            # Contar classificações para esta disciplina e turma
            classificacoes = {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0}
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua classificação
                    classificacao = result.classification
                    if classificacao in classificacoes:
                        classificacoes[classificacao] += 1
                        disciplinas_resultado[disciplina]["geral"][classificacao] += 1
            
            total_turma = sum(classificacoes.values())
            disciplinas_resultado[disciplina]["geral"]["total"] += total_turma
            
            disciplinas_resultado[disciplina]["por_turma"].append({
                "turma": turma_nome,
                "abaixo_do_basico": classificacoes["Abaixo do Básico"],
                "basico": classificacoes["Básico"],
                "adequado": classificacoes["Adequado"],
                "avancado": classificacoes["Avançado"],
                "total": total_turma
            })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        for result in class_results:
            classificacao = result.classification
            if classificacao in dados_gerais_por_turma[turma_nome]:
                dados_gerais_por_turma[turma_nome][classificacao] += 1
                dados_gerais_por_turma[turma_nome]["total"] += 1
                dados_gerais_total[classificacao] += 1
                dados_gerais_total["total"] += 1
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_resultado.items():
        resultado_final[disciplina] = {
            "por_turma": dados["por_turma"],
            "geral": {
                "abaixo_do_basico": dados["geral"]["Abaixo do Básico"],
                "basico": dados["geral"]["Básico"],
                "adequado": dados["geral"]["Adequado"],
                "avancado": dados["geral"]["Avançado"],
                "total": dados["geral"]["total"]
            }
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma_lista = []
    for turma, dados in dados_gerais_por_turma.items():
        dados_gerais_por_turma_lista.append({
            "turma": turma,
            "abaixo_do_basico": dados["Abaixo do Básico"],
            "basico": dados["Básico"],
            "adequado": dados["Adequado"],
            "avancado": dados["Avançado"],
            "total": dados["total"]
        })
    
    resultado_final["GERAL"] = {
        "por_turma": dados_gerais_por_turma_lista,
        "geral": {
            "abaixo_do_basico": dados_gerais_total["Abaixo do Básico"],
            "basico": dados_gerais_total["Básico"],
            "adequado": dados_gerais_total["Adequado"],
            "avancado": dados_gerais_total["Avançado"],
            "total": dados_gerais_total["total"]
        }
    }
    
    logging.info(f"Resultado final com disciplinas: {list(resultado_final.keys())}")
    
    return resultado_final


def _calcular_proficiencia(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula proficiência por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
            else:
                question_disciplines[question.id] = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
            else:
                question_disciplines[question.id] = "Disciplina Geral"
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter proficiências
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    # Calcular por turma e disciplina
    disciplinas_proficiencia = defaultdict(lambda: {
        "por_turma": [],
        "total_proficiencia": 0,
        "total_alunos": 0
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(list)
    dados_gerais_total_proficiencia = 0
    dados_gerais_total_alunos = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        # Para cada disciplina, calcular proficiência
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        for disciplina in disciplinas_turma:
            # Calcular proficiência para esta disciplina e turma
            proficiencias_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua proficiência
                    if result.proficiency is not None:
                        proficiencias_disciplina.append(result.proficiency)
            
            if proficiencias_disciplina:
                media_proficiencia = sum(proficiencias_disciplina) / len(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_proficiencia"] += sum(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_alunos"] += len(proficiencias_disciplina)
                
                disciplinas_proficiencia[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "proficiencia": round(media_proficiencia, 2)
                })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        proficiencias_gerais_turma = []
        for result in class_results:
            if result.proficiency is not None:
                proficiencias_gerais_turma.append(result.proficiency)
        
        if proficiencias_gerais_turma:
            media_proficiencia_geral_turma = sum(proficiencias_gerais_turma) / len(proficiencias_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "proficiencia": round(media_proficiencia_geral_turma, 2)
            })
            dados_gerais_total_proficiencia += sum(proficiencias_gerais_turma)
            dados_gerais_total_alunos += len(proficiencias_gerais_turma)
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_proficiencia.items():
        media_geral_disciplina = dados["total_proficiencia"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0
        
        resultado_final[disciplina] = {
            "por_turma": sorted(dados["por_turma"], key=lambda x: x["turma"]),
            "media_geral": round(media_geral_disciplina, 2)
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    media_geral_total = dados_gerais_total_proficiencia / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0
    
    resultado_final["GERAL"] = {
        "por_turma": sorted([dados for dados_list in dados_gerais_por_turma.values() for dados in dados_list], key=lambda x: x["turma"]),
        "media_geral": round(media_geral_total, 2)
    }
    
    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_por_disciplina(evaluation_id, question_disciplines)
    
    return {
        "por_disciplina": resultado_final,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_nota_geral(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula nota geral por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
            else:
                question_disciplines[question.id] = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
            else:
                question_disciplines[question.id] = "Disciplina Geral"
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter notas
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    # Calcular por turma e disciplina
    disciplinas_notas = defaultdict(lambda: {
        "por_turma": [],
        "total_notas": 0,
        "total_alunos": 0
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(list)
    dados_gerais_total_notas = 0
    dados_gerais_total_alunos = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        # Para cada disciplina, calcular nota
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        for disciplina in disciplinas_turma:
            # Calcular nota para esta disciplina e turma
            notas_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua nota
                    if result.grade is not None:
                        notas_disciplina.append(result.grade)
            
            if notas_disciplina:
                media_nota = sum(notas_disciplina) / len(notas_disciplina)
                disciplinas_notas[disciplina]["total_notas"] += sum(notas_disciplina)
                disciplinas_notas[disciplina]["total_alunos"] += len(notas_disciplina)
                
                disciplinas_notas[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "nota": round(media_nota, 2)
                })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        notas_gerais_turma = []
        for result in class_results:
            if result.grade is not None:
                notas_gerais_turma.append(result.grade)
        
        if notas_gerais_turma:
            media_nota_geral_turma = sum(notas_gerais_turma) / len(notas_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "nota": round(media_nota_geral_turma, 2)
            })
            dados_gerais_total_notas += sum(notas_gerais_turma)
            dados_gerais_total_alunos += len(notas_gerais_turma)
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_notas.items():
        media_geral_disciplina = dados["total_notas"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0
        
        resultado_final[disciplina] = {
            "por_turma": sorted(dados["por_turma"], key=lambda x: x["turma"]),
            "media_geral": round(media_geral_disciplina, 2)
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    media_geral_total = dados_gerais_total_notas / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0
    
    resultado_final["GERAL"] = {
        "por_turma": sorted([dados for dados_list in dados_gerais_por_turma.values() for dados in dados_list], key=lambda x: x["turma"]),
        "media_geral": round(media_geral_total, 2)
    }
    
    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_nota_por_disciplina(evaluation_id, question_disciplines)
    
    return {
        "por_disciplina": resultado_final,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_acertos_habilidade(evaluation_id: str) -> Dict[str, Any]:
    """Calcula acertos por habilidade e ranking organizados por disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por questão
    answers_by_question = defaultdict(list)
    for answer in student_answers:
        answers_by_question[answer.question_id].append(answer)
    
    # Buscar todas as habilidades para mapear ID -> código
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
        
        # Debug detalhado
        logging.info(f"Skill IDs encontrados: {skill_ids}")
        logging.info(f"Habilidades encontradas na tabela: {len(skills_dict)}")
        for skill in skills:
            logging.info(f"Skill encontrada: {skill.id} -> {skill.code}")
        
        # Verificar quais IDs não foram encontrados
        not_found = skill_ids - set(skills_dict.keys())
        if not_found:
            logging.warning(f"Skill IDs não encontrados: {not_found}")
    
    # Calcular acertos por habilidade e disciplina
    disciplinas_habilidades = defaultdict(lambda: defaultdict(lambda: {"total": 0, "acertos": 0, "questoes": []}))
    
    # Dados gerais que englobam todas as disciplinas
    habilidades_gerais = defaultdict(lambda: {"total": 0, "acertos": 0, "questoes": []})
    
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            # Se não encontrou a habilidade na tabela Skill, usar o ID como código
            if not skill_obj:
                skill_code = clean_skill_id
                disciplina = "Disciplina Geral"
                logging.warning(f"Habilidade não encontrada na tabela Skill: {clean_skill_id}")
            else:
                skill_code = skill_obj.code
                # Obter disciplina da habilidade
                if skill_obj.subject_id:
                    # Buscar a disciplina pelo subject_id
                    subject = Subject.query.get(skill_obj.subject_id)
                    if subject:
                        disciplina = subject.name
                    else:
                        disciplina = "Disciplina Geral"
                else:
                    disciplina = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                disciplina = test.subject_rel.name
                skill_code = f"Questão {question.number or 'N/A'}"
                logging.info(f"Questão {question.id} sem skill mapeada para disciplina principal: {test.subject_rel.name}")
            else:
                disciplina = "Disciplina Geral"
                skill_code = f"Questão {question.number or 'N/A'}"
                logging.warning(f"Questão {question.id} sem skill e avaliação sem disciplina principal")
        
        answers = answers_by_question.get(question.id, [])
        
        total_respostas = len(answers)
        acertos = 0
        
        for answer in answers:
            # Verificar se a resposta está correta
            if question.question_type == 'multipleChoice':
                # Para múltipla escolha, verificar se a resposta está nas alternativas corretas
                if question.alternatives:
                    correct_alternatives = [alt for alt in question.alternatives if alt.get('isCorrect', False)]
                    if any(answer.answer == alt.get('text', '') for alt in correct_alternatives):
                        acertos += 1
            else:
                # Para outros tipos, comparar com correct_answer
                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
        
        disciplinas_habilidades[disciplina][skill_code]["total"] += total_respostas
        disciplinas_habilidades[disciplina][skill_code]["acertos"] += acertos
        disciplinas_habilidades[disciplina][skill_code]["questoes"].append({
            "numero": question.number or 1,
            "acertos": acertos,
            "total": total_respostas
        })
        
        # Adicionar aos dados gerais
        habilidades_gerais[skill_code]["total"] += total_respostas
        habilidades_gerais[skill_code]["acertos"] += acertos
        habilidades_gerais[skill_code]["questoes"].append({
            "numero": question.number or 1,
            "acertos": acertos,
            "total": total_respostas
        })
    
    # Organizar resultado por disciplina
    resultado_por_disciplina = {}
    
    for disciplina, habilidades in disciplinas_habilidades.items():
        # Calcular percentuais e ranking para esta disciplina
        habilidades_ranking = []
        for skill_code, dados in habilidades.items():
            if dados["total"] > 0:
                percentual = (dados["acertos"] / dados["total"]) * 100
                habilidades_ranking.append({
                    "codigo": skill_code,
                    "descricao": f"Habilidade {skill_code}",
                    "acertos": dados["acertos"],
                    "total": dados["total"],
                    "percentual": round(percentual, 1),
                    "questoes": dados["questoes"]
                })
        
        # Ordenar por percentual (maior para menor)
        habilidades_ranking.sort(key=lambda x: x["percentual"], reverse=True)
        
        # Adicionar ranking
        for i, habilidade in enumerate(habilidades_ranking, 1):
            habilidade["ranking"] = i
        
        resultado_por_disciplina[disciplina] = {
            "habilidades": habilidades_ranking
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    habilidades_gerais_ranking = []
    for skill_code, dados in habilidades_gerais.items():
        if dados["total"] > 0:
            percentual = (dados["acertos"] / dados["total"]) * 100
            habilidades_gerais_ranking.append({
                "codigo": skill_code,
                "descricao": f"Habilidade {skill_code}",
                "acertos": dados["acertos"],
                "total": dados["total"],
                "percentual": round(percentual, 1),
                "questoes": dados["questoes"]
            })
    
    # Ordenar por percentual (maior para menor)
    habilidades_gerais_ranking.sort(key=lambda x: x["percentual"], reverse=True)
    
    # Adicionar ranking
    for i, habilidade in enumerate(habilidades_gerais_ranking, 1):
        habilidade["ranking"] = i
    
    resultado_por_disciplina["GERAL"] = {
        "habilidades": habilidades_gerais_ranking
    }
    
    return resultado_por_disciplina


def _calcular_media_municipal(evaluation_id: str) -> float:
    """Calcula média de proficiência municipal"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return 0.0
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return 0.0
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return 0.0
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return 0.0
        
        media_municipal = sum(r.proficiency for r in municipal_results) / len(municipal_results)
        return media_municipal
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal: {str(e)}")
        return 0.0


def _calcular_media_municipal_nota(evaluation_id: str) -> float:
    """Calcula média de nota municipal"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return 0.0
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return 0.0
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return 0.0
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return 0.0
        
        media_municipal = sum(r.grade for r in municipal_results) / len(municipal_results)
        return media_municipal
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal de nota: {str(e)}")
        return 0.0


def _calcular_media_municipal_por_disciplina(evaluation_id: str, question_disciplines: Dict[str, str]) -> Dict[str, float]:
    """Calcula média de proficiência municipal por disciplina"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return {}
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return {}
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return {}
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return {}
        
        # Buscar respostas dos alunos do município
        student_ids = [r.student_id for r in municipal_results]
        municipal_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == evaluation_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        
        # Agrupar respostas por aluno e disciplina
        student_discipline_results = defaultdict(lambda: defaultdict(list))
        
        for answer in municipal_answers:
            if answer.question_id in question_disciplines:
                disciplina = question_disciplines[answer.question_id]
                student_discipline_results[answer.student_id][disciplina].append(answer)
        
        # Calcular média por disciplina
        disciplinas_proficiencia = defaultdict(list)
        
        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results and result.proficiency is not None:
                for disciplina in student_discipline_results[student_id].keys():
                    disciplinas_proficiencia[disciplina].append(result.proficiency)
        
        # Calcular média para cada disciplina
        medias_por_disciplina = {}
        for disciplina, proficiencias in disciplinas_proficiencia.items():
            if proficiencias:
                media = sum(proficiencias) / len(proficiencias)
                medias_por_disciplina[disciplina] = round(media, 2)
        
        return medias_por_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal por disciplina: {str(e)}")
        return {}


def _calcular_media_municipal_nota_por_disciplina(evaluation_id: str, question_disciplines: Dict[str, str]) -> Dict[str, float]:
    """Calcula média de nota municipal por disciplina"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return {}
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return {}
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return {}
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return {}
        
        # Buscar respostas dos alunos do município
        student_ids = [r.student_id for r in municipal_results]
        municipal_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == evaluation_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        
        # Agrupar respostas por aluno e disciplina
        student_discipline_results = defaultdict(lambda: defaultdict(list))
        
        for answer in municipal_answers:
            if answer.question_id in question_disciplines:
                disciplina = question_disciplines[answer.question_id]
                student_discipline_results[answer.student_id][disciplina].append(answer)
        
        # Calcular média por disciplina
        disciplinas_notas = defaultdict(list)
        
        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results and result.grade is not None:
                for disciplina in student_discipline_results[student_id].keys():
                    disciplinas_notas[disciplina].append(result.grade)
        
        # Calcular média para cada disciplina
        medias_por_disciplina = {}
        for disciplina, notas in disciplinas_notas.items():
            if notas:
                media = sum(notas) / len(notas)
                medias_por_disciplina[disciplina] = round(media, 2)
        
        return medias_por_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal de nota por disciplina: {str(e)}")
        return {}


@bp.errorhandler(Exception)
def handle_error(error):
    """Handler de erros para o blueprint"""
    logging.error(f"Erro no blueprint de relatórios: {str(error)}")
    return jsonify({"error": "Erro interno do servidor"}), 500
