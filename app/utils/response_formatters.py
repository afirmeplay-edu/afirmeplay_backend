from app.models.educationStage import EducationStage
from app.models.city import City
from app.models.school import School
from app.models.studentClass import Class
from app.models.grades import Grade

def format_question_response(q, exclude_fields=None):
    if exclude_fields is None:
        exclude_fields = []

    response = {
        'id': q.id,
        'number': q.number,
        'text': q.text,
        'formattedText': q.formatted_text,
        'options': q.alternatives,
        'skills': q.skill,
        'difficulty': q.difficulty_level,
        'solution': q.correct_answer,
        'formattedSolution': q.formatted_solution,
        'secondStatement': q.secondstatement,
        'type': q.question_type,
        'value': q.value,
        'topics': q.topics,
        'version': q.version,
        'updatedAt': q.updated_at.isoformat() if q.updated_at else None,
        'lastModifiedBy': {'id': q.last_modifier.id, 'name': q.last_modifier.name} if q.last_modifier else None,
    }

    if 'title' not in exclude_fields:
        response['title'] = q.title
    if 'description' not in exclude_fields:
        response['description'] = q.description
    if 'subject' not in exclude_fields:
        response['subject'] = {'id': q.subject.id, 'name': q.subject.name} if q.subject else None
    if 'grade' not in exclude_fields:
        response['grade'] = {'id': q.grade.id, 'name': q.grade.name} if q.grade else None
    if 'educationStage' not in exclude_fields:
        response['educationStage'] = {'id': q.education_stage.id, 'name': q.education_stage.name} if q.education_stage else None
    if 'createdBy' not in exclude_fields:
        response['createdAt'] = q.created_at.isoformat() if q.created_at else None
        response['createdBy'] = {'id': q.creator.id, 'name': q.creator.name} if q.creator else None
    
    # Remove chaves com valor None para uma resposta mais limpa
    return {k: v for k, v in response.items() if v is not None}

def format_test_response(test):
    # Campos do Test que são análogos aos da Question e que serão excluídos da formatação da questão
    exclude_from_question = ['subject', 'grade', 'createdBy', 'title', 'description']
    
    # Busca os nomes para os campos que armazenam IDs
    course_obj = EducationStage.query.get(test.course) if test.course else None
    
    municipalities_list = []
    if test.municipalities:
        municipalities_objs = City.query.filter(City.id.in_(test.municipalities)).all()
        municipalities_list = [{'id': m.id, 'name': m.name} for m in municipalities_objs]

    schools_list = []
    if test.schools:
        schools_objs = School.query.filter(School.id.in_(test.schools)).all()
        schools_list = [{'id': s.id, 'name': s.name} for s in schools_objs]

    # Buscar informações sobre as classes onde a avaliação foi aplicada
    applied_classes_info = []
    if test.class_tests:
        for ct in test.class_tests:
            class_obj = Class.query.get(ct.class_id)
            if class_obj:
                school_obj = School.query.get(class_obj.school_id)
                grade_obj = Grade.query.get(class_obj.grade_id)
                
                applied_classes_info.append({
                    "class_test_id": ct.id,
                    "class": {
                        "id": class_obj.id,
                        "name": class_obj.name,
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

    return {
        'id': test.id,
        'title': test.title,
        'description': test.description,
        'type': test.type,
        'subject': {'id': test.subject_rel.id, 'name': test.subject_rel.name} if test.subject_rel else None,
        'grade': {'id': test.grade.id, 'name': test.grade.name} if test.grade else None,
        'max_score': test.max_score,
        'time_limit': test.time_limit.isoformat() if test.time_limit else None,
        'createdBy': {'id': test.creator.id, 'name': test.creator.name} if test.creator else None,
        'createdAt': test.created_at.isoformat() if test.created_at else None,
        'updatedAt': test.updated_at.isoformat() if test.updated_at else None,
        'course': {'id': course_obj.id, 'name': course_obj.name} if course_obj else None,
        'municipalities': municipalities_list,
        'schools': schools_list,
        'model': test.model,
        'subjects_info': test.subjects_info,
        'applied_classes': applied_classes_info,
        'questions': [format_question_response(q, exclude_fields=exclude_from_question) for q in test.questions]
    } 