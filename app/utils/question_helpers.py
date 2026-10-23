"""
Helper functions para buscar questões considerando multitenant
"""
from app import db

AFIRME_LER_QUESTION_IN_PLAY_ERROR = (
    "Questões do Afirme Ler não podem ser usadas no Afirme Play."
)


def play_questions_only(query):
    """Restringe uma query de Question às questões de origem Afirme Play."""
    from app.models.question import Question, QUESTION_ORIGIN_PLAY

    return query.filter(Question.origin == QUESTION_ORIGIN_PLAY)


def afirme_ler_question_ids(question_ids):
    """Devolve, entre os ids informados, os que são questões do Afirme Ler."""
    from app.models.question import Question, QUESTION_ORIGIN_LER

    ids = list({str(qid) for qid in (question_ids or []) if qid})
    if not ids:
        return []
    rows = (
        Question.query.with_entities(Question.id)
        .filter(Question.id.in_(ids), Question.origin == QUESTION_ORIGIN_LER)
        .all()
    )
    return sorted(str(row[0]) for row in rows)


def question_ids_from_payload(questions):
    """Ids de questões existentes num payload `questions` de avaliação do Play."""
    if not isinstance(questions, list):
        return []
    return [
        item.get('id') for item in questions
        if isinstance(item, dict) and item.get('id')
    ]


def get_questions_from_test(test_id, order_by_test_question=True):
    """
    Busca questões de uma avaliação considerando multitenant.
    
    As questões estão em public.question; o ORM qualifica pelo schema do modelo.
    
    Args:
        test_id (str): ID da avaliação
        order_by_test_question (bool): Se True, ordena pelas questões na ordem do test
        
    Returns:
        list: Lista de objetos Question ordenados
    """
    from app.models.question import Question
    from app.models.testQuestion import TestQuestion
    
    # Buscar IDs das questões da avaliação
    query = TestQuestion.query.filter_by(test_id=test_id)
    if order_by_test_question:
        query = query.order_by(TestQuestion.order)
    
    test_questions = query.all()
    question_ids = [tq.question_id for tq in test_questions]
    
    if not question_ids:
        return []
    
    questions = Question.query.filter(Question.id.in_(question_ids)).all()
    
    # Se precisar ordenar, fazer aqui
    if order_by_test_question and questions:
        # Criar dicionário para acesso rápido
        questions_dict = {q.id: q for q in questions}
        # Ordenar pela ordem original dos test_questions
        ordered_questions = []
        for tq in test_questions:
            if tq.question_id in questions_dict:
                ordered_questions.append(questions_dict[tq.question_id])
        return ordered_questions
    
    return questions


def get_question_ids_from_test(test_id, order_by=True):
    """
    Busca apenas os IDs das questões de uma avaliação.
    
    Args:
        test_id (str): ID da avaliação
        order_by (bool): Se True, ordena pelas questões na ordem do test
        
    Returns:
        list: Lista de IDs (strings) das questões
    """
    from app.models.testQuestion import TestQuestion
    
    query = TestQuestion.query.filter_by(test_id=test_id)
    if order_by:
        query = query.order_by(TestQuestion.order)
    
    test_questions = query.all()
    return [tq.question_id for tq in test_questions]
