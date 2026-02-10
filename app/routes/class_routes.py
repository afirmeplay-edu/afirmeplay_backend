from flask import Blueprint, request, jsonify
from app.models.studentClass import Class
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators import requires_city_context
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import logging
from app.models.student import Student
from app.models.school import School
from app.models.grades import Grade
from app.models.city import City
from app.models.educationStage import EducationStage
from app.decorators.role_required import get_current_tenant_id

bp = Blueprint('classes', __name__, url_prefix="/classes")

@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"error": "Database error occurred", "details": str(error)}), 500

@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"error": "Data integrity error", "details": str(error)}), 400

@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"error": "An unexpected error occurred", "details": str(error)}), 500

@bp.route('/filtered', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
@requires_city_context
def get_filtered_classes():
    """
    Busca turmas com filtros avançados
    
    Query Parameters:
    - municipality_id: ID do município
    - school_id: ID da escola
    - grade_id: ID da série/ano
    - education_stage_id: ID do estágio educacional
    
    Returns:
        Lista de turmas filtradas com informações completas
    """
    try:
        # Extrair parâmetros de filtro
        municipality_id = request.args.get('municipality_id')
        school_id = request.args.get('school_id')
        grade_id = request.args.get('grade_id')
        education_stage_id = request.args.get('education_stage_id')
        
        # Query base com joins
        query = db.session.query(
            Class,
            School,
            Grade,
            City,
            db.func.count(Student.id).label('students_count')
        ).join(
            School, Class.school_id == cast(School.id, PostgresUUID)
        ).join(
            City, School.city_id == City.id
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).outerjoin(
            Student, Class.id == Student.class_id
        ).group_by(
            Class.id, School.id, Grade.id, City.id
        )
        
        # Aplicar filtros
        if municipality_id:
            query = query.filter(City.id == municipality_id)
            
        if school_id:
            # Converter school_id para UUID (Class.school_id é UUID)
            school_id_uuid = ensure_uuid(school_id)
            if school_id_uuid:
                query = query.filter(Class.school_id == school_id_uuid)
            
        if grade_id:
            # grade_id já é UUID, mas vamos garantir
            grade_id_uuid = ensure_uuid(grade_id)
            if grade_id_uuid:
                query = query.filter(Grade.id == grade_id_uuid)
            
        if education_stage_id:
            query = query.filter(Grade.education_stage_id == education_stage_id)
        
        # Executar query
        classes = query.all()
        
        if not classes:
            return jsonify({
                "data": [],
                "total": 0,
                "message": "Nenhuma turma encontrada com os filtros aplicados"
            }), 200
        
        # Formatar resultados
        results = []
        for class_obj, school, grade, city, students_count in classes:
            results.append({
                "id": class_obj.id,
                "name": class_obj.name,
                "school_id": class_obj.school_id,
                "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None,
                "students_count": students_count,
                "school": {
                    "id": school.id,
                    "name": school.name,
                    "address": school.address
                } if school else None,
                "grade": {
                    "id": grade.id,
                    "name": grade.name
                } if grade else None,
                "city": {
                    "id": city.id,
                    "name": city.name,
                    "state": city.state
                } if city else None
            })
        
        return jsonify({
            "data": results,
            "total": len(results),
            "filters_applied": {
                "municipality_id": municipality_id,
                "school_id": school_id,
                "grade_id": grade_id,
                "education_stage_id": education_stage_id
            }
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar turmas filtradas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar turmas", "details": str(e)}), 500

@bp.route('/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_classes_by_school(school_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Verificar se a escola existe
        school = School.query.get(school_id)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404

        # Verificar permissões
        if user['role'] == "admin":
            # Admin pode ver qualquer escola
            pass
        elif user['role'] == "professor":
            # Professor só pode ver turmas das escolas onde está vinculado
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Professor não encontrado"}), 404
            
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            teacher_school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_id not in teacher_school_ids:
                return jsonify({"error": "Você não tem permissão para visualizar turmas desta escola"}), 403
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador só podem ver turmas da sua escola
            from app.models.manager import Manager
            
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager:
                return jsonify({"error": "Diretor/Coordenador não encontrado na tabela manager"}), 404
            
            if not manager.school_id or manager.school_id != school_id:
                return jsonify({"error": "Você não tem permissão para visualizar turmas desta escola"}), 403
        else:
            # TecAdmin só pode ver escolas do seu município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id or school.city_id != city_id:
                return jsonify({"error": "Você não tem permissão para visualizar turmas desta escola"}), 403

        # Query with explicit joins including EducationStage
        classes = db.session.query(
            Class,
            School,
            Grade,
            EducationStage,
            db.func.count(Student.id).label('students_count')
        ).join(
            School, Class.school_id == cast(School.id, PostgresUUID)
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).outerjoin(
            EducationStage, Grade.education_stage_id == EducationStage.id
        ).outerjoin(
            Student, Class.id == Student.class_id
        ).filter(
            Class.school_id == ensure_uuid(school_id) if school_id else None
        ).group_by(
            Class.id, School.id, Grade.id, EducationStage.id
        ).all()
        
        if not classes:
            return jsonify([]), 200  # Return empty list if no classes found

        return jsonify([{
            "id": c.id,
            "name": c.name,
            "school_id": c.school_id,
            "grade_id": str(c.grade_id) if c.grade_id else None,
            "students_count": students_count,
            "school": {
                "id": school.id,
                "name": school.name
            } if school else None,
            "grade": {
                "id": grade.id,
                "name": grade.name,
                "education_stage": {
                    "id": education_stage.id,
                    "name": education_stage.name
                } if education_stage else None
            } if grade else None
        } for c, school, grade, education_stage, students_count in classes]), 200

    except Exception as e:
        logging.error(f"Error getting classes by school: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting classes by school", "details": str(e)}), 500

@bp.route('/by-school/<string:school_id>', methods=['GET'])
@jwt_required()
def get_classes_by_school_alias(school_id):
    """
    Alias para /classes/school/<school_id> - Turmas por escola
    """
    return get_classes_by_school(school_id)

@bp.route('', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_classes():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404

        # Query base com joins
        query = db.session.query(
            Class,
            School,
            Grade
        ).join(
            School, Class.school_id == cast(School.id, PostgresUUID)
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        )

        # Aplicar filtros baseado na role
        if user['role'] == "admin":
            # Admin vê todas as turmas
            classes = query.all()
        elif user['role'] == "professor":
            # Professor vê turmas das escolas onde está vinculado
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Professor não encontrado"}), 404
            
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if school_ids:
                classes = query.filter(Class.school_id.in_(school_ids)).all()
            else:
                return jsonify({"error": "Professor não está alocado em nenhuma escola"}), 400
        elif user['role'] in ["diretor", "coordenador"]:
            # Diretor e coordenador veem turmas apenas de sua escola
            from app.models.teacher import Teacher
            from app.models.schoolTeacher import SchoolTeacher
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify({"error": "Diretor/Coordenador não encontrado"}), 404
            
            teacher_school = SchoolTeacher.query.filter_by(teacher_id=teacher.id).first()
            if not teacher_school:
                return jsonify({"error": "Diretor/Coordenador não está vinculado a nenhuma escola"}), 400
            
            # Converter school_id para UUID (Class.school_id é UUID)
            school_id_uuid = ensure_uuid(teacher_school.school_id)
            if school_id_uuid:
                classes = query.filter(Class.school_id == school_id_uuid).all()
            else:
                return jsonify({"error": "ID de escola inválido"}), 400
        else:
            # TecAdmin vê turmas de todas as escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "ID da cidade não disponível"}), 400
            
            # A query já tem JOIN com School usando cast, então apenas filtrar
            classes = query.filter(School.city_id == city_id).all()

        return jsonify([{
            "id": c.id,
            "name": c.name,
            "school_id": c.school_id,
            "grade_id": str(c.grade_id) if c.grade_id else None,
            "school": {
                "id": school.id,
                "name": school.name
            } if school else None,
            "grade": {
                "id": grade.id,
                "name": grade.name
            } if grade else None
        } for c, school, grade in classes]), 200
    except Exception as e:
        logging.error(f"Error getting classes: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting classes", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['GET'])
@jwt_required()
def get_class(class_id):
    try:
        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400
        
        # Query with explicit joins
        result = db.session.query(
            Class,
            School,
            Grade,
            Student
        ).join(
            School, Class.school_id == cast(School.id, PostgresUUID)
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).outerjoin(
            Student, Class.id == Student.class_id
        ).filter(
            Class.id == class_id_uuid
        ).all()

        if not result:
            return jsonify({"error": "Class not found"}), 404

        class_obj, school, grade = result[0][:3]
        students = [s for _, _, _, s in result if s is not None]

        return jsonify({
            "id": class_obj.id,
            "name": class_obj.name,
            "school_id": class_obj.school_id,
            "grade_id": str(class_obj.grade_id) if class_obj.grade_id else None,
            "school": {
                "id": school.id,
                "name": school.name
            } if school else None,
            "grade": {
                "id": grade.id,
                "name": grade.name
            } if grade else None,
            "students": [{"id": s.id, "name": s.name} for s in students]
        }), 200
    except Exception as e:
        logging.error(f"Error getting class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error getting class", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['PUT'])
@jwt_required()
def update_class(class_id):
    try:
        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400
        
        class_obj = Class.query.get(class_id_uuid)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        if "name" in data:
            class_obj.name = data["name"]
        if "school_id" in data:
            # Converter school_id para UUID (Class.school_id é UUID)
            school_id_uuid = ensure_uuid(data["school_id"])
            if school_id_uuid:
                class_obj.school_id = school_id_uuid
        if "grade_id" in data:
            # Validar que o curso da série está vinculado à escola
            from app.models.grades import Grade
            from app.models.schoolCourse import SchoolCourse
            
            grade = Grade.query.get(data["grade_id"])
            if not grade:
                return jsonify({"error": "Série não encontrada"}), 404
            
            # Determinar qual escola usar (a atual ou a nova se estiver sendo atualizada)
            school_id_to_check = data.get("school_id", class_obj.school_id)
            
            # Verificar se o curso (education_stage) da série está vinculado à escola
            school_course = SchoolCourse.query.filter_by(
                school_id=school_id_to_check,
                education_stage_id=grade.education_stage_id
            ).first()
            
            if not school_course:
                school = School.query.get(school_id_to_check)
                school_name = school.name if school else "escola"
                return jsonify({
                    "error": "Curso não vinculado à escola",
                    "details": f"A série '{grade.name}' pertence ao curso '{grade.education_stage.name}', mas este curso não está vinculado à escola '{school_name}'. Por favor, vincule o curso à escola antes de atualizar a turma."
                }), 400
            
            class_obj.grade_id = data["grade_id"]

        db.session.commit()
        return jsonify({"message": "Class updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error updating class", "details": str(e)}), 500

@bp.route('/<string:class_id>', methods=['DELETE'])
@jwt_required()
def delete_class(class_id):
    """
    Rota DELETE para excluir uma turma.
    Inclui logging detalhado e captura de contexto completo.
    """
    # Obter informações do usuário autenticado para logging
    user_info = None
    try:
        user_info = get_current_user_from_token()
    except Exception:
        pass  # Continuar mesmo se não conseguir obter usuário
    
    try:
        # Log inicial da requisição
        logging.info(
            f"🗑️ DELETE /classes/{class_id} - "
            f"Usuário: {user_info.get('email', 'N/A') if user_info else 'N/A'} "
            f"({user_info.get('id', 'N/A') if user_info else 'N/A'}) - "
            f"IP: {request.remote_addr if request else 'N/A'}"
        )
        
        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400
        
        class_obj = Class.query.get(class_id_uuid)
        if not class_obj:
            logging.warning(
                f"⚠️ Tentativa de deletar turma inexistente: {class_id} - "
                f"Usuário: {user_info.get('email', 'N/A') if user_info else 'N/A'}"
            )
            return jsonify({"error": "Class not found"}), 404

        # Log informações da turma antes de deletar
        logging.info(
            f"📋 Informações da turma a ser deletada: "
            f"ID={class_id}, Nome={class_obj.name}, "
            f"Escola={class_obj.school_id if class_obj.school_id else 'N/A'}, "
            f"Série={class_obj.grade_id if class_obj.grade_id else 'N/A'}"
        )

        # 1. Desvincular alunos
        from app.models.student import Student
        students = Student.query.filter_by(class_id=class_id).all()
        student_ids = [s.id for s in students]
        logging.info(
            f"👥 Desvinculando {len(students)} alunos da turma {class_id}. "
            f"IDs dos alunos: {student_ids[:10]}{'...' if len(student_ids) > 10 else ''}"
        )
        for student in students:
            student.class_id = None
        
        # 2. Excluir registros em ClassTest
        from app.models.classTest import ClassTest
        class_tests = ClassTest.query.filter_by(class_id=class_id).all()
        test_ids = [ct.test_id for ct in class_tests]
        logging.info(
            f"📝 Excluindo {len(class_tests)} registros em ClassTest para turma {class_id}. "
            f"IDs dos testes: {test_ids[:10]}{'...' if len(test_ids) > 10 else ''}"
        )
        for ct in class_tests:
            db.session.delete(ct)
        
        # 3. Excluir registros em ClassSubject
        from app.models.classSubject import ClassSubject
        class_subjects = ClassSubject.query.filter_by(class_id=class_id).all()
        subject_ids = [cs.subject_id for cs in class_subjects]
        logging.info(
            f"📚 Excluindo {len(class_subjects)} registros em ClassSubject para turma {class_id}. "
            f"IDs das disciplinas: {subject_ids[:10]}{'...' if len(subject_ids) > 10 else ''}"
        )
        for cs in class_subjects:
            db.session.delete(cs)
        
        # 4. Excluir a turma
        logging.info(f"🗑️ Excluindo turma {class_id} (nome: {class_obj.name})")
        db.session.delete(class_obj)
        
        # Commit com log de sucesso
        db.session.commit()
        logging.info(
            f"✅ Turma {class_id} excluída com sucesso. "
            f"Usuário: {user_info.get('email', 'N/A') if user_info else 'N/A'} - "
            f"Alunos desvinculados: {len(students)}, "
            f"ClassTests excluídos: {len(class_tests)}, "
            f"ClassSubjects excluídos: {len(class_subjects)}"
        )
        return jsonify({"message": "Class deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        # Log detalhado do erro com contexto completo
        error_context = {
            "route": f"DELETE /classes/{class_id}",
            "class_id": class_id,
            "user_id": user_info.get('id') if user_info else None,
            "user_email": user_info.get('email') if user_info else None,
            "ip": request.remote_addr if request else None,
            "error_type": type(e).__name__,
            "error_message": str(e)
        }
        logging.error(
            f"❌ ERRO ao deletar turma {class_id}: {str(e)} | "
            f"Contexto: {error_context}",
            exc_info=True
        )
        return jsonify({"error": "Error deleting class", "details": str(e)}), 500

@bp.route('', methods=['POST'])
@jwt_required()
def create_class():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate required fields
        required_fields = ["name", "school_id"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Validar se a escola existe
        from app.models.school import School
        school = School.query.get(data["school_id"])
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404

        # Se grade_id foi fornecido, validar que o curso da série está vinculado à escola
        if data.get("grade_id"):
            from app.models.grades import Grade
            from app.models.schoolCourse import SchoolCourse
            
            grade = Grade.query.get(data["grade_id"])
            if not grade:
                return jsonify({"error": "Série não encontrada"}), 404
            
            # Verificar se o curso (education_stage) da série está vinculado à escola
            school_course = SchoolCourse.query.filter_by(
                school_id=data["school_id"],
                education_stage_id=grade.education_stage_id
            ).first()
            
            if not school_course:
                return jsonify({
                    "error": "Curso não vinculado à escola",
                    "details": f"A série '{grade.name}' pertence ao curso '{grade.education_stage.name}', mas este curso não está vinculado à escola '{school.name}'. Por favor, vincule o curso à escola antes de criar a turma."
                }), 400

        # Create new class
        # Converter school_id para UUID (Class.school_id é UUID)
        school_id_uuid = ensure_uuid(data["school_id"])
        if not school_id_uuid:
            return jsonify({"error": "ID de escola inválido"}), 400
        
        grade_id_uuid = None
        if data.get("grade_id"):
            grade_id_uuid = ensure_uuid(data["grade_id"])
        
        new_class = Class(
            name=data["name"],
            school_id=school_id_uuid,
            grade_id=grade_id_uuid  # Optional field
        )

        db.session.add(new_class)
        db.session.commit()

        return jsonify({
            "message": "Class created successfully",
            "class": {
                "id": new_class.id,
                "name": new_class.name,
                "school_id": new_class.school_id,
                "grade_id": str(new_class.grade_id) if new_class.grade_id else None
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        logging.error(f"Integrity error while creating class: {str(e)}")
        return jsonify({"error": "Data integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating class: {str(e)}", exc_info=True)
        return jsonify({"error": "Error creating class", "details": str(e)}), 500

@bp.route('/<string:class_id>/add_student', methods=['PUT', 'POST'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def add_student_to_class(class_id):
    try:
        logging.info(f"Attempting to add student to class ID: {class_id}")

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Aceitar tanto student_id (singular) quanto student_ids (plural)
        student_ids = []
        if "student_id" in data:
            student_ids = [data["student_id"]]
        elif "student_ids" in data:
            student_ids = data["student_ids"]
        else:
            return jsonify({"error": "Missing student_id or student_ids field"}), 400

        if not student_ids:
            return jsonify({"error": "No student IDs provided"}), 400

        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400
        
        class_obj = Class.query.get(class_id_uuid)
        if not class_obj:
            logging.warning(f"Class not found with ID: {class_id}")
            return jsonify({"error": "Class not found"}), 404

        # Processar múltiplos alunos
        added_students = []
        errors = []
        
        for student_id in student_ids:
            try:
                student = Student.query.get(student_id)
                if not student:
                    errors.append(f"Student {student_id} not found")
                    continue

                # Check if student is already in this class
                if student.class_id == class_id:
                    errors.append(f"Student {student_id} is already in class {class_id}")
                    continue

                # Update the student's class_id and school_id
                student.class_id = class_id
                student.school_id = class_obj.school_id
                
                # Atualizar city_id do usuário se necessário
                if student.user.city_id != class_obj.school.city_id:
                    student.user.city_id = class_obj.school.city_id
                    logging.info(f"Atualizando city_id do aluno {student.user.id} para {class_obj.school.city_id}")
                
                added_students.append(student_id)
                logging.info(f"Student {student_id} successfully added to class {class_id}")
                
            except Exception as e:
                errors.append(f"Error processing student {student_id}: {str(e)}")
                logging.error(f"Error adding student {student_id} to class: {str(e)}")
        
        if added_students:
            db.session.commit()
            logging.info(f"Successfully added {len(added_students)} students to class {class_id}")
        
        return jsonify({
            "message": f"Students processed for class {class_id}",
            "added_students": added_students,
            "total_added": len(added_students),
            "errors": errors if errors else None
        }), 200 if added_students else 400

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error while adding student to class: {str(e)}")
        return jsonify({"message": "Internal server error while adding student to class", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error in add_student_to_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500

@bp.route('/<string:class_id>/remove_student', methods=['PUT'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def remove_student_from_class(class_id):
    try:
        logging.info(f"Attempting to remove student from class ID: {class_id}")

        data = request.get_json()
        if not data or "student_id" not in data:
            return jsonify({"error": "No data provided or missing student_id"}), 400

        student_id = data["student_id"]

        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"error": "ID de turma inválido"}), 400
        
        class_obj = Class.query.get(class_id_uuid)
        if not class_obj:
            logging.warning(f"Class not found with ID: {class_id}")
            return jsonify({"error": "Class not found"}), 404

        student = Student.query.get(student_id)
        if not student:
            logging.warning(f"Student not found with ID: {student_id}")
            return jsonify({"error": "Student not found"}), 404

        # Check if student is actually in this class (optional)
        if student.class_id != class_id:
            return jsonify({"message": f"Student {student_id} is not in class {class_id}"}), 200

        # Update the student's class_id to null
        student.class_id = None
        
        # Verificar se o aluno ainda está em outras turmas da mesma escola
        if student.school_id:
            other_classes_in_school = Student.query.filter(
                Student.user_id == student.user.id,
                Student.school_id == student.school_id,
                Student.class_id.isnot(None)
            ).count()
            
            # Se não estiver em nenhuma turma da escola, desvincular da escola também
            if other_classes_in_school == 0:
                logging.info(f"Aluno {student_id} não está em nenhuma turma da escola {student.school_id}, desvinculando da escola")
                student.school_id = None
            else:
                logging.info(f"Aluno {student_id} ainda está em {other_classes_in_school} turma(s) da escola {student.school_id}")
        
        # Atualizar city_id do usuário se necessário (quando aluno é movido para outra escola)
        if student.school_id:
            school = School.query.get(student.school_id)
            if school and school.city_id != student.user.city_id:
                student.user.city_id = school.city_id
                logging.info(f"Atualizando city_id do aluno {student.user.id} para {school.city_id}")
        
        db.session.commit()

        logging.info(f"Student {student_id} successfully removed from class {class_id}")

        return jsonify({"message": f"Student successfully removed from class {class_id}"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error while removing student from class: {str(e)}")
        return jsonify({"message": "Internal server error while removing student from class", "details": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Unexpected error in remove_student_from_class route: {str(e)}", exc_info=True)
        return jsonify({"message": "An unexpected error occurred", "details": str(e)}), 500 

@bp.route('/<string:class_id>/teachers', methods=['GET'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def get_class_teachers(class_id):
    try:
        # Converter class_id para UUID (Class.id é UUID)
        class_id_uuid = ensure_uuid(class_id)
        if not class_id_uuid:
            return jsonify({"erro": "ID de turma inválido"}), 400
        
        # Verificar se a turma existe
        class_obj = Class.query.get(class_id_uuid)
        if not class_obj:
            return jsonify({"erro": "Turma não encontrada"}), 404

        # Buscar professores da turma
        from app.models.teacherClass import TeacherClass
        from app.models.teacher import Teacher
        from app.models.user import User
        
        professores = db.session.query(
            Teacher,
            User,
            TeacherClass
        ).join(
            User, Teacher.user_id == User.id
        ).join(
            TeacherClass, Teacher.id == TeacherClass.teacher_id
        ).filter(
            TeacherClass.class_id == class_id
        ).all()

        resultado = []
        for professor, usuario, vinculo in professores:
            resultado.append({
                "professor": {
                    "id": professor.id,
                    "name": professor.name,
                    "email": usuario.email,
                    "registration": professor.registration,
                    "birth_date": str(professor.birth_date) if professor.birth_date else None,
                    "city_id": usuario.city_id
                },
                "usuario": {
                    "id": usuario.id,
                    "name": usuario.name,
                    "email": usuario.email,
                    "registration": usuario.registration,
                    "role": usuario.role.value
                },
                "vinculo_turma": {
                    "teacher_class_id": vinculo.id,
                    "class_id": vinculo.class_id
                }
            })

        return jsonify({
            "mensagem": "Professores da turma encontrados com sucesso",
            "turma": {
                "id": class_obj.id,
                "name": class_obj.name,
                "school_id": class_obj.school_id
            },
            "professores": resultado
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados ao buscar professores da turma: {str(e)}")
        return jsonify({"erro": "Ocorreu um erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado ao buscar professores da turma: {str(e)}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro inesperado", "detalhes": str(e)}), 500 