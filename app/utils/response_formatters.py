from app.models.educationStage import EducationStage
from app.models.city import City
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
import uuid
import logging


def _is_valid_uuid(uuid_string):
    """Verifica se uma string é um UUID válido."""
    if not uuid_string:
        return False
    try:
        uuid.UUID(str(uuid_string))
        return True
    except (ValueError, TypeError):
        return False


def _get_education_stage_safely(course_value):
    """
    Busca EducationStage de forma segura, tratando tanto UUIDs quanto nomes.
    
    Args:
        course_value: Pode ser um UUID (string) ou nome do curso
        
    Returns:
        EducationStage object ou None se não encontrado
    """
    if not course_value:
        return None
    
    try:
        # Primeiro tenta como UUID
        if _is_valid_uuid(course_value):
            return EducationStage.query.get(course_value)
        
        # Se não for UUID, tenta buscar por nome
        return EducationStage.query.filter_by(name=course_value).first()
        
    except Exception as e:
        logging.warning(f"Erro ao buscar EducationStage para valor '{course_value}': {str(e)}")
        return None


def format_question_response(q, exclude_fields=None):
    if exclude_fields is None:
        exclude_fields = []

    response = {
        'id': q.id,
        'number': q.number if q.number is not None else 1,
        'text': q.text if q.text else '',
        'formattedText': q.formatted_text if q.formatted_text else q.text if q.text else '',
        'options': q.alternatives if q.alternatives else [],
        'skills': q.skill.split(',') if q.skill else [],
        'difficulty': q.difficulty_level if q.difficulty_level else 'Médio',
        'solution': q.correct_answer if q.correct_answer else '',
        'formattedSolution': q.formatted_solution if q.formatted_solution else '',
        'secondStatement': q.secondstatement if q.secondstatement else '',
        'type': q.question_type if q.question_type else 'multipleChoice',
        'value': q.value if q.value is not None else 1,
        'topics': q.topics if q.topics else [],
        'version': q.version if q.version is not None else 1,
        'updatedAt': q.updated_at.isoformat() if q.updated_at else None,
        'lastModifiedBy': {'id': q.last_modifier.id, 'name': q.last_modifier.name} if q.last_modifier else None,
    }

    if 'title' not in exclude_fields:
        response['title'] = q.title if q.title else ''
    if 'description' not in exclude_fields:
        response['description'] = q.description if q.description else ''
    if 'subject' not in exclude_fields:
        response['subject'] = {'id': q.subject.id, 'name': q.subject.name} if q.subject else None
    if 'grade' not in exclude_fields:
        response['grade'] = {'id': q.grade.id, 'name': q.grade.name} if q.grade else None
    if 'educationStage' not in exclude_fields:
        response['educationStage'] = {'id': q.education_stage.id, 'name': q.education_stage.name} if q.education_stage else None
    if 'createdBy' not in exclude_fields:
        response['createdAt'] = q.created_at.isoformat() if q.created_at else None
        response['createdBy'] = {'id': q.creator.id, 'name': q.creator.name} if q.creator else None
    
    # Não remover campos None - retornar todos os campos
    return response


def format_test_response(test):
    # Campos do Test que são análogos aos da Question e que serão excluídos da formatação da questão
    exclude_from_question = ['grade', 'createdBy', 'title', 'description']
    
    # Busca os nomes para os campos que armazenam IDs de forma segura
    course_obj = _get_education_stage_safely(test.course)
    
    municipalities_list = []
    if test.municipalities:
        try:
            municipalities_objs = City.query.filter(City.id.in_(test.municipalities)).all()
            municipalities_list = [{'id': m.id, 'name': m.name} for m in municipalities_objs]
        except Exception as e:
            logging.warning(f"Erro ao buscar municípios: {str(e)}")
            municipalities_list = []

    schools_list = []
    if test.schools:
        try:
            schools_objs = School.query.filter(School.id.in_(test.schools)).all()
            schools_list = [{'id': s.id, 'name': s.name} for s in schools_objs]
        except Exception as e:
            logging.warning(f"Erro ao buscar escolas: {str(e)}")
            schools_list = []

    # Buscar informações sobre as classes onde a avaliação foi aplicada
    applied_classes_info = []
    total_students = 0
    
    if test.class_tests:
        for ct in test.class_tests:
            try:
                class_obj = Class.query.get(ct.class_id)
                if class_obj:
                    school_obj = School.query.get(class_obj.school_id)
                    grade_obj = Grade.query.get(class_obj.grade_id)
                    
                    # Contar alunos na turma
                    students_count = len(class_obj.students) if class_obj.students else 0
                    total_students += students_count
                    
                    applied_classes_info.append({
                        "class_test_id": ct.id,
                        "class": {
                            "id": class_obj.id,
                            "name": class_obj.name,
                            "students_count": students_count,
                            "school": {
                                "id": school_obj.id,
                                "name": school_obj.name
                            } if school_obj else None,
                            "grade": {
                                "id": grade_obj.id,
                                "name": grade_obj.name
                            } if grade_obj else None
                        },
                        "application": ct.application.isoformat() if ct.application else None,
                        "expiration": ct.expiration.isoformat() if ct.expiration else None
                    })
            except Exception as e:
                logging.warning(f"Erro ao processar class_test {ct.id}: {str(e)}")
                continue

    # Calcular duração dinamicamente
    duration = 90  # Duração padrão em minutos
    try:
        if test.time_limit and test.end_time:
            # Calcular duração real baseada no end_time - time_limit
            duration_delta = test.end_time - test.time_limit
            duration = int(duration_delta.total_seconds() / 60)  # Converter para minutos
        elif test.time_limit:
            # Se não tiver end_time, usar duração padrão de 90 minutos
            duration = 90
    except Exception as e:
        logging.warning(f"Erro ao calcular duração: {str(e)}")
        duration = 90

    return {
        'id': test.id,
        'title': test.title,
        'description': test.description,
        'type': test.type,
        'subject': {'id': test.subject_rel.id, 'name': test.subject_rel.name} if test.subject_rel else None,
        'grade': {'id': test.grade.id, 'name': test.grade.name} if test.grade else None,
        'max_score': test.max_score,
        'time_limit': test.time_limit.isoformat() if test.time_limit else None,
        'end_time': test.end_time.isoformat() if test.end_time else None,
        'duration': duration,
        'createdBy': {'id': test.creator.id, 'name': test.creator.name} if test.creator else None,
        'createdAt': test.created_at.isoformat() if test.created_at else None,
        'updatedAt': test.updated_at.isoformat() if test.updated_at else None,
        'course': {'id': course_obj.id, 'name': course_obj.name} if course_obj else None,
        'municipalities': municipalities_list,
        'municipalities_count': len(municipalities_list),
        'schools': schools_list,
        'schools_count': len(schools_list),
        # Para compatibilidade com o front-end, adicionar também school como primeiro da lista
        'school': schools_list[0] if schools_list else None,
        'model': test.model,
        'subjects_info': test.subjects_info,
        'status': test.status,
        'applied_classes': applied_classes_info,
        'applied_classes_count': len(applied_classes_info),
        'total_students': total_students,
        'questions': [format_question_response(q, exclude_fields=exclude_from_question) for q in test.questions]
    } 