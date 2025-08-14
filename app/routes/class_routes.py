from flask import Blueprint, request, jsonify
from app.models.studentClass import Class
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
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
            School, Class.school_id == School.id
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
            query = query.filter(School.id == school_id)
            
        if grade_id:
            query = query.filter(Grade.id == grade_id)
            
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
def get_classes_by_school(school_id):
    try:
        # Query with explicit joins including EducationStage
        classes = db.session.query(
            Class,
            School,
            Grade,
            EducationStage,
            db.func.count(Student.id).label('students_count')
        ).join(
            School, Class.school_id == School.id
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).outerjoin(
            EducationStage, Grade.education_stage_id == EducationStage.id
        ).outerjoin(
            Student, Class.id == Student.class_id
        ).filter(
            Class.school_id == school_id
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
            School, Class.school_id == School.id
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
            
            classes = query.filter(Class.school_id == teacher_school.school_id).all()
        else:
            # TecAdmin vê turmas de todas as escolas do município
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify({"error": "ID da cidade não disponível"}), 400
            
            classes = query.join(School).filter(School.city_id == city_id).all()

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
        # Query with explicit joins
        result = db.session.query(
            Class,
            School,
            Grade,
            Student
        ).join(
            School, Class.school_id == School.id
        ).outerjoin(
            Grade, Class.grade_id == Grade.id
        ).outerjoin(
            Student, Class.id == Student.class_id
        ).filter(
            Class.id == class_id
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
        class_obj = Class.query.get(class_id)
        if not class_obj:
            return jsonify({"error": "Class not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        if "name" in data:
            class_obj.name = data["name"]
        if "school_id" in data:
            class_obj.school_id = data["school_id"]
        if "grade_id" in data:
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
    try:
        import logging
        class_obj = Class.query.get(class_id)
        if not class_obj:
            logging.error(f"Turma {class_id} não encontrada.")
            return jsonify({"error": "Class not found"}), 404

        # 1. Desvincular alunos
        from app.models.student import Student
        students = Student.query.filter_by(class_id=class_id).all()
        logging.info(f"Desvinculando {len(students)} alunos da turma {class_id}")
        for student in students:
            student.class_id = None
        
        # 2. Excluir registros em ClassTest
        from app.models.classTest import ClassTest
        class_tests = ClassTest.query.filter_by(class_id=class_id).all()
        logging.info(f"Excluindo {len(class_tests)} registros em ClassTest para turma {class_id}")
        for ct in class_tests:
            db.session.delete(ct)
        
        # 3. Excluir registros em ClassSubject
        from app.models.classSubject import ClassSubject
        class_subjects = ClassSubject.query.filter_by(class_id=class_id).all()
        logging.info(f"Excluindo {len(class_subjects)} registros em ClassSubject para turma {class_id}")
        for cs in class_subjects:
            db.session.delete(cs)
        
        # 4. Excluir a turma
        logging.info(f"Excluindo turma {class_id}")
        db.session.delete(class_obj)
        db.session.commit()
        logging.info(f"Turma {class_id} excluída com sucesso.")
        return jsonify({"message": "Class deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting class: {str(e)}", exc_info=True)
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

        # Create new class
        new_class = Class(
            name=data["name"],
            school_id=data["school_id"],
            grade_id=data.get("grade_id")  # Optional field
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

@bp.route('/<string:class_id>/add_student', methods=['PUT'])
@jwt_required()
@role_required("admin", "diretor", "coordenador", "professor", "tecadm")
def add_student_to_class(class_id):
    try:
        logging.info(f"Attempting to add student to class ID: {class_id}")

        data = request.get_json()
        if not data or "student_id" not in data:
            return jsonify({"error": "No data provided or missing student_id"}), 400

        student_id = data["student_id"]

        class_obj = Class.query.get(class_id)
        if not class_obj:
            logging.warning(f"Class not found with ID: {class_id}")
            return jsonify({"error": "Class not found"}), 404

        student = Student.query.get(student_id)
        if not student:
            logging.warning(f"Student not found with ID: {student_id}")
            return jsonify({"error": "Student not found"}), 404

        # Check if student is already in this class (optional)
        if student.class_id == class_id:
            return jsonify({"message": f"Student {student_id} is already in class {class_id}"}), 200

        # Update the student's class_id
        student.class_id = class_id

        db.session.commit()

        logging.info(f"Student {student_id} successfully added to class {class_id}")

        return jsonify({"message": f"Student successfully added to class {class_id}"}), 200

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

        class_obj = Class.query.get(class_id)
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
        # Verificar se a turma existe
        class_obj = Class.query.get(class_id)
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