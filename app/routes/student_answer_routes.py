from flask import Blueprint, request, jsonify
from app import db
from app.models.studentAnswer import StudentAnswer

bp = Blueprint('student_answer', __name__, url_prefix='/answers')

@bp.route('', methods=['POST'])
def submit_answers():
    data = request.get_json()
    student_id = data.get('student_id')
    test_id = data.get('test_id')
    answers = data.get('answers', [])

    if not student_id or not test_id or not answers:
        return jsonify({'error': 'Dados incompletos'}), 400

    for ans in answers:
        question_id = ans.get('question_id')
        answer = ans.get('answer')
        if not question_id or answer is None:
            continue
        student_answer = StudentAnswer(
            student_id=student_id,
            test_id=test_id,
            question_id=question_id,
            answer=answer
        )
        db.session.add(student_answer)
    db.session.commit()
    return jsonify({'message': 'Respostas salvas com sucesso!'}), 201 