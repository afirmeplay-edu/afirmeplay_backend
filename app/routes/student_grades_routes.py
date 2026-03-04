from flask import Blueprint, request, jsonify
from app.models.student import Student
from app.models.user import User, RoleEnum
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from app.models.question import Question
from app.models.studentAnswer import StudentAnswer
from app.models.testQuestion import TestQuestion
from app.models.educationStage import EducationStage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
import logging
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from app import db
from typing import Dict, List, Optional, Any
from app.services.evaluation_result_service import EvaluationResultService
from app.services.student_ranking_service import StudentRankingService
from app.services.achievement_service import (
    get_conquistas,
    get_redeemed_keys_from_user,
    get_coin_value_for_medal,
    student_has_medal,
)
from app.balance.services.coin_service import CoinService
import uuid

bp = Blueprint('student_grades', __name__, url_prefix="/students")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

def _get_classification_from_proficiency(proficiency: float) -> str:
    """Determina a classificação baseada na proficiência"""
    if proficiency < 200:
        return "Abaixo do Básico"
    elif proficiency < 250:
        return "Básico"
    elif proficiency < 300:
        return "Adequado"
    else:
        return "Avançado"

def _get_student_general_stats(student_id: str) -> Dict[str, Any]:
    """Calcula estatísticas gerais do aluno baseadas em todas as avaliações"""
    try:
        # Buscar todos os resultados do aluno
        results = EvaluationResult.query.filter_by(student_id=student_id).all()
        
        if not results:
            return {
                "total_evaluations": 0,
                "general_proficiency": 0.0,
                "general_grade": 0.0,
                "general_classification": "Sem avaliações",
                "total_correct_answers": 0,
                "total_questions_answered": 0
            }
        
        # Calcular médias
        total_proficiency = sum(r.proficiency for r in results)
        total_grade = sum(r.grade for r in results)
        total_correct = sum(r.correct_answers for r in results)
        total_questions = sum(r.total_questions for r in results)
        
        avg_proficiency = total_proficiency / len(results)
        avg_grade = total_grade / len(results)
        
        classification = _get_classification_from_proficiency(avg_proficiency)
        
        return {
            "total_evaluations": len(results),
            "general_proficiency": round(avg_proficiency, 2),
            "general_grade": round(avg_grade, 2),
            "general_classification": classification,
            "total_correct_answers": total_correct,
            "total_questions_answered": total_questions
        }
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas gerais do aluno {student_id}: {str(e)}")
        return {}

def _calculate_student_rankings(student_id: str, evaluation_id: Optional[str] = None) -> Dict[str, Any]:
    """Wrapper temporário para manter compatibilidade com chamadas existentes."""
    try:
        return StudentRankingService.get_rankings(student_id, evaluation_id)
    except Exception as e:
        logging.error(f"Erro ao calcular rankings do aluno {student_id}: {str(e)}")
        return {}

def _get_evaluation_specific_stats(student_id: str, evaluation_id: str) -> Dict[str, Any]:
    """Busca estatísticas específicas de uma avaliação"""
    try:
        # Buscar resultado específico da avaliação
        result = EvaluationResult.query.filter_by(
            student_id=student_id,
            test_id=evaluation_id
        ).first()
        
        if not result:
            return {}
        
        return {
            "evaluation_id": evaluation_id,
            "proficiency": result.proficiency,
            "grade": result.grade,
            "classification": result.classification,
            "correct_answers": result.correct_answers,
            "total_questions": result.total_questions,
            "score_percentage": result.score_percentage,
            "calculated_at": result.calculated_at.isoformat() if result.calculated_at else None
        }
        
    except Exception as e:
        logging.error(f"Erro ao buscar estatísticas específicas do aluno {student_id} na avaliação {evaluation_id}: {str(e)}")
        return {}

def _validate_student_access(user: dict, student_id: str) -> bool:
    """Valida se o usuário tem acesso aos dados do aluno"""
    try:
        # Admin tem acesso total
        if user['role'] == 'admin':
            return True
        
        # Aluno só pode ver seus próprios dados
        if user['role'] == 'aluno':
            # Para aluno, o student_id já é do próprio usuário
            student = Student.query.filter_by(user_id=user['id']).first()
            return student and student.id == student_id
        
        # Professor, diretor, coordenador - verificar se o aluno está em suas escolas
        if user['role'] in ['professor', 'diretor', 'coordenador']:
            student = Student.query.get(student_id)
            
            if not student or not student.school_id:
                return False
            
            if user['role'] == 'professor':
                # Professor: verificar se está alocado na escola do aluno
                from app.models.teacher import Teacher
                from app.models.schoolTeacher import SchoolTeacher
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if not teacher:
                    return False
                
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                teacher_school_ids = [ts.school_id for ts in teacher_schools]
                
                return student.school_id in teacher_school_ids
            
            elif user['role'] in ['diretor', 'coordenador']:
                # Diretor/Coordenador: verificar se está na mesma escola
                from app.models.manager import Manager
                
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager:
                    return False
                
                return manager.school_id == student.school_id
        
        # TecAdm: verificar se o aluno está no mesmo município
        elif user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return False
            
            student = Student.query.get(student_id)
            
            school = School.query.get(student.school_id) if student and student.school_id else None
            return student and school and school.city_id == city_id
        
        return False
        
    except Exception as e:
        logging.error(f"Erro ao validar acesso do usuário {user.get('id')} ao aluno {student_id}: {str(e)}")
        return False

@bp.route('/<string:user_id>/grades/general', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_student_general_grades(user_id):
    """
    Retorna as notas gerais do aluno (médias de todas as avaliações)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar o aluno pelo user_id
        student = Student.query.filter_by(user_id=user_id).first()
        
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Validar acesso ao aluno
        if not _validate_student_access(user, student.id):
            return jsonify({"error": "Você não tem permissão para acessar os dados deste aluno"}), 403
        
        # Calcular estatísticas gerais
        general_stats = _get_student_general_stats(student.id)
        
        # Calcular rankings
        rankings = _calculate_student_rankings(student.id)
        
        # Buscar dados relacionados
        school = School.query.get(student.school_id) if student.school_id else None
        class_obj = Class.query.get(student.class_id) if student.class_id else None
        
        # Montar resposta
        response_data = {
            "user_id": user_id,
            "student_id": student.id,
            "student_name": student.name,
            "student_registration": student.registration,
            "school_name": school.name if school else None,
            "class_name": class_obj.name if class_obj else None,
            **general_stats,
            "rankings": rankings
        }
        
        return jsonify({
            "success": True,
            "data": response_data,
            "message": "Dados gerais do aluno obtidos com sucesso"
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter notas gerais do aluno {user_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter dados do aluno", "details": str(e)}), 500

@bp.route('/<string:user_id>/grades/evaluation/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_student_evaluation_grades(user_id, evaluation_id):
    """
    Retorna as notas do aluno em uma avaliação específica
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar o aluno pelo user_id
        student = Student.query.filter_by(user_id=user_id).first()
        
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404
        
        # Validar acesso ao aluno
        if not _validate_student_access(user, student.id):
            return jsonify({"error": "Você não tem permissão para acessar os dados deste aluno"}), 403
        
        # Buscar estatísticas específicas da avaliação
        evaluation_stats = _get_evaluation_specific_stats(student.id, evaluation_id)
        
        if not evaluation_stats:
            return jsonify({
                "success": True,
                "data": {
                    "user_id": user_id,
                    "student_id": student.id,
                    "student_name": student.name,
                    "evaluation_id": evaluation_id,
                    "evaluation_name": test.title,
                    "message": "Aluno não respondeu esta avaliação"
                },
                "message": "Aluno não possui resultados para esta avaliação"
            }), 200
        
        # Calcular rankings específicos da avaliação
        rankings = _calculate_student_rankings(student.id, evaluation_id)
        
        # Buscar resultados detalhados por disciplina (quando aplicável)
        subject_results: List[Dict[str, Any]] = []
        try:
            # Verificar se há informações de disciplinas
            has_subjects_info = isinstance(test.subjects_info, list) and len(test.subjects_info) > 0
            if has_subjects_info:
                # Buscar questões ordenadas da avaliação
                test_question_ids = [
                    tq.question_id for tq in TestQuestion.query.filter_by(
                        test_id=evaluation_id
                    ).order_by(TestQuestion.order).all()
                ]

                questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []

                if questions:
                    # Buscar respostas do aluno
                    answers = StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        student_id=student.id
                    ).all()

                    if answers:
                        # Determinar nome do curso (replicando lógica do serviço)
                        course_name = "Anos Iniciais"
                        if test.course:
                            try:
                                course_uuid = uuid.UUID(str(test.course))
                                course_obj = EducationStage.query.get(course_uuid)
                                if course_obj:
                                    course_name = course_obj.name
                            except Exception:
                                course_obj = EducationStage.query.get(str(test.course))
                                if course_obj:
                                    course_name = course_obj.name

                        subject_results = EvaluationResultService._calculate_subject_specific_results(
                            test_id=evaluation_id,
                            student_id=student.id,
                            questions=questions,
                            answers=answers,
                            course_name=course_name
                        )
        except Exception as subject_err:
            logging.error(
                f"Erro ao montar resultados por disciplina para aluno {student.id} na avaliação {evaluation_id}: {subject_err}",
                exc_info=True
            )
            subject_results = []

        # Buscar dados relacionados
        school = School.query.get(student.school_id) if student.school_id else None
        class_obj = Class.query.get(student.class_id) if student.class_id else None
        
        # Montar resposta
        response_data = {
            "user_id": user_id,
            "student_id": student.id,
            "student_name": student.name,
            "student_registration": student.registration,
            "school_name": school.name if school else None,
            "class_name": class_obj.name if class_obj else None,
            "evaluation_name": test.title,
            **evaluation_stats,
            "rankings": rankings,
            "subject_results": subject_results
        }
        
        return jsonify({
            "success": True,
            "data": response_data,
            "message": "Dados da avaliação obtidos com sucesso"
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter notas da avaliação {evaluation_id} do aluno {user_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter dados da avaliação", "details": str(e)}), 500


# ---------------------------------------------------------------------------
# Conquistas (achievements) - sem novas tabelas; resgate de moedas em User.traits
# ---------------------------------------------------------------------------

@bp.route('/me/conquistas', methods=['GET'])
@jwt_required()
@role_required("aluno", "admin", "professor", "coordenador", "diretor", "tecadm")
def get_my_conquistas():
    """
    Retorna conquistas do aluno logado (estado, medalha, progresso, moedas_valor, resgatado).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        student = Student.query.filter_by(user_id=user["id"]).first()
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404

        user_model = User.query.get(student.user_id) if student.user_id else None
        redeemed_keys = get_redeemed_keys_from_user(user_model)

        result = get_conquistas(student.id, redeemed_keys=redeemed_keys)
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Erro ao obter conquistas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter conquistas", "details": str(e)}), 500


@bp.route('/<string:student_id>/conquistas', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_student_conquistas(student_id):
    """
    Retorna conquistas de um aluno (para professor/admin/diretor/coordenador/tecadm).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        student = Student.query.get(student_id)
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404

        if not _validate_student_access(user, student.id):
            return jsonify({"error": "Você não tem permissão para acessar os dados deste aluno"}), 403

        user_model = User.query.get(student.user_id) if student.user_id else None
        redeemed_keys = get_redeemed_keys_from_user(user_model)

        result = get_conquistas(student.id, redeemed_keys=redeemed_keys)
        return jsonify(result), 200
    except Exception as e:
        logging.error(f"Erro ao obter conquistas do aluno {student_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter conquistas", "details": str(e)}), 500


@bp.route('/me/conquistas/resgatar', methods=['POST'])
@jwt_required()
@role_required("aluno")
def resgatar_conquista():
    """
    Resgata moedas por uma conquista+medalha. Uma vez por par (conquista, medalha).
    Body: { "achievement_id": "...", "medalha": "bronze"|"prata"|"ouro"|"platina" }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        student = Student.query.filter_by(user_id=user["id"]).first()
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404

        data = request.get_json() or {}
        achievement_id = (data.get("achievement_id") or "").strip()
        medalha = (data.get("medalha") or "").strip().lower()

        if not achievement_id or not medalha:
            return jsonify({"error": "achievement_id e medalha são obrigatórios"}), 400

        if medalha not in ("bronze", "prata", "ouro", "platina"):
            return jsonify({"error": "medalha inválida"}), 400

        user_model = User.query.get(student.user_id) if student.user_id else None
        if not user_model:
            return jsonify({"error": "Usuário do aluno não encontrado"}), 404

        traits = dict(user_model.traits) if user_model.traits and isinstance(user_model.traits, dict) else {}
        redeemed_list = list(traits.get("achievements_redeemed") or [])

        chave = f"{achievement_id}_{medalha}"
        if chave in redeemed_list:
            return jsonify({"error": "Conquista já resgatada para esta medalha"}), 400

        if not student_has_medal(student.id, achievement_id, medalha):
            return jsonify({"error": "Você ainda não atingiu esta medalha para esta conquista"}), 400

        valor = get_coin_value_for_medal(achievement_id, medalha)
        if valor is None or valor <= 0:
            return jsonify({"error": "Valor em moedas não definido para esta conquista/medalha"}), 400

        CoinService.credit_coins(
            student.id,
            valor,
            reason="achievement_redeem",
            description=chave,
        )

        redeemed_list.append(chave)
        traits["achievements_redeemed"] = redeemed_list
        user_model.traits = traits
        db.session.commit()

        novo_saldo = CoinService.get_balance(student.id)
        # Resposta enriquecida para o front exibir recompensa (ex.: "Conquista X (Ouro) resgatada! +50 moedas")
        conquista_nome = _get_achievement_name(achievement_id)
        return jsonify({
            "message": "Moedas resgatadas com sucesso",
            "moedas_creditadas": valor,
            "novo_saldo": novo_saldo,
            "conquista_nome": conquista_nome,
            "medalha": medalha,
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao resgatar conquista: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao resgatar conquista", "details": str(e)}), 500


def _get_achievement_name(achievement_id: str) -> Optional[str]:
    """Retorna o nome de exibição da conquista pelo id."""
    from app.services.achievement_service import (
        ACHIEVEMENTS_CONFIG,
        PERFEccionISTA_CONFIG,
    )
    if achievement_id == "perfeccionista":
        return (PERFEccionISTA_CONFIG or {}).get("nome") or "Perfeccionista"
    for cfg in (ACHIEVEMENTS_CONFIG or []):
        if cfg.get("id") == achievement_id:
            return cfg.get("nome") or achievement_id
    return achievement_id


@bp.route('/me/conquistas/resgatar-todas', methods=['POST'])
@jwt_required()
@role_required("aluno")
def resgatar_todas_conquistas():
    """
    Resgata em uma única ação todas as conquistas desbloqueadas cujas moedas
    ainda não foram resgatadas. O aluno pode usar um botão "Resgatar recompensas"
    para ganhar todas as moedas pendentes e aumentar a sensação de recompensa.
    Body: opcional {}.
    Retorna: moedas_creditadas_total, itens_resgatados, novo_saldo.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        student = Student.query.filter_by(user_id=user["id"]).first()
        if not student:
            return jsonify({"error": "Aluno não encontrado"}), 404

        user_model = User.query.get(student.user_id) if student.user_id else None
        if not user_model:
            return jsonify({"error": "Usuário do aluno não encontrado"}), 404

        traits = dict(user_model.traits) if user_model.traits and isinstance(user_model.traits, dict) else {}
        redeemed_list = list(traits.get("achievements_redeemed") or [])

        data = get_conquistas(student.id, redeemed_keys=redeemed_list)
        conquistas = data.get("conquistas") or []

        itens_resgatados: List[Dict[str, Any]] = []
        total_moedas = 0

        for c in conquistas:
            achievement_id = c.get("id")
            medalha = c.get("medalha_atual")
            if not medalha or c.get("resgatado"):
                continue
            valor = c.get("moedas_valor") or 0
            if valor <= 0:
                continue
            chave = f"{achievement_id}_{medalha}"
            if chave in redeemed_list:
                continue

            CoinService.credit_coins(
                student.id,
                valor,
                reason="achievement_redeem",
                description=chave,
            )
            redeemed_list.append(chave)
            total_moedas += valor
            itens_resgatados.append({
                "achievement_id": achievement_id,
                "nome": c.get("nome") or _get_achievement_name(achievement_id),
                "medalha": medalha,
                "moedas": valor,
            })

        if itens_resgatados:
            traits["achievements_redeemed"] = redeemed_list
            user_model.traits = traits
            db.session.commit()

        novo_saldo = CoinService.get_balance(student.id)

        if not itens_resgatados:
            return jsonify({
                "message": "Nenhuma conquista pendente para resgatar",
                "moedas_creditadas_total": 0,
                "itens_resgatados": [],
                "novo_saldo": novo_saldo,
            }), 200

        return jsonify({
            "message": f"Você resgatou {len(itens_resgatados)} conquista(s) e ganhou {total_moedas} moedas!",
            "moedas_creditadas_total": total_moedas,
            "itens_resgatados": itens_resgatados,
            "novo_saldo": novo_saldo,
        }), 200
    except Exception as e:
        logging.error(f"Erro ao resgatar todas as conquistas: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao resgatar conquistas", "details": str(e)}), 500
