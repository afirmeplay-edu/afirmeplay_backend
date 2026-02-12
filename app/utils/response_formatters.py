from app.models.educationStage import EducationStage
from app.models.city import City
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.subject import Subject
import uuid
import logging
from sqlalchemy.exc import SQLAlchemyError


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


def _get_all_subjects_from_test(test):
    """
    Busca todas as disciplinas de uma avaliação, tanto a única quanto as múltiplas.
    
    Args:
        test: Objeto Test
        
    Returns:
        Lista de dicionários com {'id': id, 'name': name} das disciplinas
    """
    subjects_list = []
    
    try:
        # 1. Verificar se há disciplina única (campo subject)
        if test.subject and test.subject_rel and hasattr(test, 'subject_rel') and test.subject_rel:
            subjects_list.append({
                'id': test.subject_rel.id,
                'name': test.subject_rel.name
            })
        
        # 2. Verificar se há múltiplas disciplinas (campo subjects_info)
        if test.subjects_info and isinstance(test.subjects_info, list) and hasattr(test, 'subjects_info'):
            for subject_info in test.subjects_info:
                # Verificar se subject_info é um dicionário com id
                if isinstance(subject_info, dict) and subject_info and 'id' in subject_info:
                    subject_id = subject_info['id']
                    
                    # Buscar o nome da disciplina no banco
                    subject_obj = Subject.query.get(subject_id)
                    if subject_obj and hasattr(subject_obj, 'id') and hasattr(subject_obj, 'name'):
                        # Verificar se já não foi adicionada (evitar duplicatas)
                        if not any(s.get('id') == subject_obj.id for s in subjects_list):
                            subjects_list.append({
                                'id': subject_obj.id,
                                'name': subject_obj.name
                            })
                # Se subject_info é apenas um ID (string)
                elif isinstance(subject_info, str) and subject_info and _is_valid_uuid(subject_info):
                    subject_obj = Subject.query.get(subject_info)
                    if subject_obj and hasattr(subject_obj, 'id') and hasattr(subject_obj, 'name'):
                        # Verificar se já não foi adicionada (evitar duplicatas)
                        if not any(s.get('id') == subject_obj.id for s in subjects_list):
                            subjects_list.append({
                                'id': subject_obj.id,
                                'name': subject_obj.name
                            })
                            
    except Exception as e:
        logging.warning(f"Erro ao buscar disciplinas para teste {test.id}: {str(e)}")
    
    return subjects_list


def normalize_alternatives_with_correct(alternatives, correct_answer=None):
    """
    Garante que todas as alternativas tenham id, text e isCorrect
    """
    if not alternatives:
        return []
    
    normalized = []
    for i, alt in enumerate(alternatives):
        # Determinar o ID da alternativa
        if isinstance(alt, dict) and alt.get('id') and alt.get('id') != 'None':
            option_id = alt.get('id')
        else:
            option_id = f"option-{i}"
        
        # Determinar o texto da alternativa
        if isinstance(alt, dict):
            text = alt.get('text') or alt.get('answer') or ''
        elif isinstance(alt, str):
            text = alt
        else:
            text = str(alt) if alt else ''
        
        # Determinar se está correto
        is_correct = False
        if isinstance(alt, dict):
            is_correct = alt.get('isCorrect') or alt.get('is_correct') or False
        
        # Se temos correct_answer, usar para determinar isCorrect
        if correct_answer and not is_correct:
            # Comparar por ID se correct_answer é um ID
            if option_id == correct_answer:
                is_correct = True
            # Comparar por texto se correct_answer é um texto
            elif text.strip().lower() == correct_answer.strip().lower():
                is_correct = True
            # Comparar por letra (A, B, C, D...)
            elif correct_answer.strip().upper() in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                if i < len(letters) and letters[i] == correct_answer.strip().upper():
                    is_correct = True
        
        normalized_alt = {
            "id": option_id,
            "text": text,
            "isCorrect": is_correct
        }
        normalized.append(normalized_alt)
    
    return normalized


def validate_question_data(question_data):
    """
    Valida se a questão tem dados coerentes
    """
    alternatives = question_data.get('alternatives', [])
    
    # Verificar se tem alternativas
    if not alternatives:
        return True  # Pode ser questão discursiva
    
    # Se tem alternativas, verificar se pelo menos uma está correta
    correct_count = sum(1 for alt in alternatives if alt.get('isCorrect'))
    if correct_count == 0:
        # Tentar determinar pela correct_answer
        correct_answer = question_data.get('correct_answer')
        if correct_answer:
            # Há um gabarito definido, isso é válido
            return True
        else:
            logging.warning(f"Questão {question_data.get('id')} não tem alternativa correta definida")
    
    # Verificar se todos os IDs são únicos
    ids = [alt.get('id') for alt in alternatives if isinstance(alt, dict)]
    if len(ids) != len(set(ids)):
        logging.warning(f"Questão {question_data.get('id')} tem IDs de alternativas duplicados")
    
    return True


def format_question_response(q, exclude_fields=None):
    if exclude_fields is None:
        exclude_fields = []

    # Normalizar alternativas com isCorrect
    normalized_alternatives = normalize_alternatives_with_correct(q.alternatives, q.correct_answer)
    
    response = {
        'id': q.id,
        'number': q.number if q.number is not None else 1,
        'text': q.text if q.text else '',
        'formattedText': q.formatted_text if q.formatted_text else q.text if q.text else '',
        'alternatives': normalized_alternatives,  # Campo obrigatório com estrutura correta
        'options': normalized_alternatives,  # Alias para compatibilidade
        'skills': q.skill.split(',') if q.skill and isinstance(q.skill, str) else [],
        'difficulty': q.difficulty_level if q.difficulty_level else 'Médio',
        'solution': q.correct_answer if q.correct_answer else '',
        'correct_answer': q.correct_answer if q.correct_answer else '',  # Campo obrigatório
        'formattedSolution': q.formatted_solution if q.formatted_solution else '',
        'secondStatement': q.secondstatement if q.secondstatement else '',
        'type': q.question_type if q.question_type else 'multipleChoice',
        'value': q.value if q.value is not None else 1,
        'topics': q.topics if q.topics and isinstance(q.topics, list) else [],
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
    """
    Formata a resposta de um teste com todas as informações relacionadas.
    Inclui tratamento de erros com rollback para evitar transações abortadas.
    """
    from app import db
    
    try:
        # Campos do Test que são análogos aos da Question e que serão excluídos da formatação da questão
        exclude_from_question = ['grade', 'createdBy', 'title', 'description']
        
        # Busca os nomes para os campos que armazenam IDs de forma segura
        course_obj = _get_education_stage_safely(test.course)
        
        # Buscar todas as disciplinas da avaliação (única + múltiplas)
        all_subjects = _get_all_subjects_from_test(test)
        
        municipalities_list = []
        if test.municipalities:
            try:
                # Verificar se municipalities é uma lista ou string
                municipality_ids = []
                if isinstance(test.municipalities, list):
                    municipality_ids = test.municipalities
                elif isinstance(test.municipalities, str):
                    municipality_ids = [test.municipalities]
                
                if municipality_ids:
                    municipalities_objs = City.query.filter(City.id.in_(municipality_ids)).all()
                    municipalities_list = [{'id': m.id, 'name': m.name} for m in municipalities_objs]
            except Exception as e:
                db.session.rollback()
                logging.warning(f"Erro ao buscar municípios: {str(e)}")
                municipalities_list = []

        schools_list = []
        if test.schools:
            try:
                # Verificar se schools é uma lista ou string
                school_ids = []
                if isinstance(test.schools, list):
                    school_ids = test.schools
                elif isinstance(test.schools, str):
                    school_ids = [test.schools]
                
                if school_ids:
                    schools_objs = School.query.filter(School.id.in_(school_ids)).all()
                    schools_list = [{'id': s.id, 'name': s.name} for s in schools_objs]
            except Exception as e:
                db.session.rollback()
                logging.warning(f"Erro ao buscar escolas: {str(e)}")
                schools_list = []

        # Buscar informações completas das classes específicas (campo classes)
        classes_info = []
        if test.classes:
            try:
                class_ids = []
                if isinstance(test.classes, list):
                    class_ids = test.classes
                elif isinstance(test.classes, str):
                    class_ids = [test.classes]
                
                if class_ids:
                    # Converter class_ids para UUID (Class.id é UUID)
                    from app.utils.uuid_helpers import ensure_uuid_list
                    class_ids_uuids = ensure_uuid_list(class_ids)
                    specific_classes = Class.query.filter(Class.id.in_(class_ids_uuids)).all()
                    
                    for class_obj in specific_classes:
                        try:
                            # class_obj.school_id é UUID, School.id é VARCHAR - converter para string
                            school_obj = School.query.filter(School.id == str(class_obj.school_id)).first()
                            grade_obj = Grade.query.get(class_obj.grade_id)
                            
                            # Contar alunos na turma
                            students_count = len(class_obj.students) if class_obj.students else 0
                            
                            classes_info.append({
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
                            })
                        except Exception as e:
                            db.session.rollback()
                            logging.warning(f"Erro ao processar classe {class_obj.id}: {str(e)}")
                            continue
            except Exception as e:
                db.session.rollback()
                logging.warning(f"Erro ao buscar classes específicas: {str(e)}")
                classes_info = []
        
        # Buscar informações sobre as classes onde a avaliação foi aplicada
        applied_classes_info = []
        total_students = 0
        
        # Primeira prioridade: usar class_tests (quando a avaliação foi aplicada)
        # Carregar class_tests de forma explícita para evitar problemas de transação
        from app.models.classTest import ClassTest
        class_tests_list = ClassTest.query.filter_by(test_id=str(test.id)).all()
        
        if class_tests_list:
            for ct in class_tests_list:
                try:
                    class_obj = Class.query.get(ct.class_id)
                    if class_obj:
                        # class_obj.school_id é UUID, School.id é VARCHAR - converter para string
                        school_obj = School.query.filter(School.id == str(class_obj.school_id)).first()
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
                            "application": ct.application if ct.application else None,
                            "expiration": ct.expiration if ct.expiration else None
                        })
                except Exception as e:
                    db.session.rollback()
                    logging.warning(f"Erro ao processar class_test {ct.id}: {str(e)}")
                    continue
        
        # Fallback: usar schools quando não há class_tests (avaliação ainda não aplicada)
        elif test.schools:
            try:
                school_ids = []
                if isinstance(test.schools, list):
                    school_ids = test.schools
                elif isinstance(test.schools, str):
                    school_ids = [test.schools]
                
                # Buscar todas as turmas das escolas selecionadas
                if school_ids:
                    # Class.school_id e school.id são VARCHAR; comparar como string (ver db_uuid_normalization.md)
                    from app.utils.uuid_helpers import ensure_uuid_list
                    uuids = ensure_uuid_list(school_ids)
                    school_ids_str = [str(s) for s in (uuids if uuids else school_ids)]
                    classes_objs = Class.query.filter(Class.school_id.in_(school_ids_str)).all()
                    
                    for class_obj in classes_objs:
                        try:
                            # class_obj.school_id é UUID, School.id é VARCHAR - converter para string
                            school_obj = School.query.filter(School.id == str(class_obj.school_id)).first()
                            grade_obj = Grade.query.get(class_obj.grade_id)
                            
                            # Contar alunos na turma
                            students_count = len(class_obj.students) if class_obj.students else 0
                            total_students += students_count
                            
                            applied_classes_info.append({
                                "class_test_id": None,  # Não há class_test ainda
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
                                "application": None,  # Ainda não aplicada
                                "expiration": None    # Ainda não aplicada
                            })
                        except Exception as e:
                            db.session.rollback()
                            logging.warning(f"Erro ao processar classe {class_obj.id}: {str(e)}")
                            continue
            except Exception as e:
                db.session.rollback()
                logging.warning(f"Erro ao buscar turmas das escolas: {str(e)}")
                applied_classes_info = []

        # Usar duração do modelo ou calcular dinamicamente como fallback
        duration = test.duration if test.duration is not None else 90  # Duração padrão em minutos
        if duration is None:
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

        # Determinar se a avaliação foi aplicada baseado na existência de class_tests
        is_applied = len(class_tests_list) > 0 if class_tests_list else False

        return {
        'id': test.id,
        'title': test.title,
        'description': test.description,
        'type': test.type,
        'subject': all_subjects[0] if all_subjects else None,  # Primeira disciplina para compatibilidade
        'subjects': all_subjects,  # TODAS as disciplinas selecionadas
        'subjects_count': len(all_subjects),  # Quantidade de disciplinas
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
        'classes': classes_info,  # Array com informações completas das classes específicas
        'classes_count': len(classes_info),  # Contagem de classes
        'model': test.model,
        'subjects_info': test.subjects_info,  # Manter o campo original para compatibilidade
        'status': test.status,
        'is_applied': is_applied,  # Campo explícito indicando se a avaliação foi aplicada
        'applied_classes': applied_classes_info,
        'applied_classes_count': len(applied_classes_info),
        'total_students': total_students,
        'questions': [format_question_response(q, exclude_fields=exclude_from_question) for q in test.questions]
    }
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro SQLAlchemy em format_test_response para teste {test.id}: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro inesperado em format_test_response para teste {test.id}: {str(e)}", exc_info=True)
        raise 