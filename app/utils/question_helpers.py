"""
Helper functions para buscar questões considerando multitenant
"""
from app import db
from sqlalchemy import text


def get_questions_from_test(test_id, order_by_test_question=True):
    """
    Busca questões de uma avaliação considerando multitenant.
    
    As questões estão em public.question, mas o search_path pode estar em city_xxx.
    Esta função muda temporariamente para public, busca as questões e restaura o search_path.
    
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
    
    # MULTITENANT FIX: Buscar questões em public.question
    # Salvar search_path atual
    current_search_path = db.session.execute(text("SHOW search_path")).fetchone()[0]
    
    try:
        # Mudar para public para buscar questões
        db.session.execute(text("SET search_path TO public"))
        
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        
    finally:
        # Restaurar search_path original (sempre executado, mesmo se houver erro)
        db.session.execute(text(f"SET search_path TO {current_search_path}"))
    
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
