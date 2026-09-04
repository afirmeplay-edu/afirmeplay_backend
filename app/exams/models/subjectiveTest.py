# -*- coding: utf-8 -*-
"""
Avaliação subjetiva: entidade própria, separada de Test/Question.

Diferente da avaliação online, aqui a prova em si é física/impressa e fica fora do
sistema — só a ESTRUTURA é cadastrada (quantidade de questões e, para cada uma, uma
habilidade digitada livremente). Não há enunciado, alternativas nem gabarito
estruturado (ver SubjectiveQuestion). A correção é sempre manual, célula a célula
(aluno x questão), usando a rubrica SIM/PARCIAL/NAO/BRANCO (ver SubjectiveResult).

`shadow_test_id` aponta para um registro "espelho" em tenant.test (evaluation_mode
'subjective', sem questões reais nele), criado internamente só para reaproveitar o
pipeline de EvaluationResult/relatórios já existente (mesma estratégia da TestSession
sintética em SubjectiveEvaluationService) — não deve ser exposto/editado pelo frontend.
"""
from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSON
import uuid

# Tipo/rótulo da avaliação subjetiva. Texto livre por natureza (só serve de rótulo na
# UI, não muda regra de cálculo nem de escopo) — diferente de Test.type (AVALIACAO,
# SIMULADO, OLIMPIADA), que tem validações próprias.
SUBJECTIVE_TEST_TYPES = ('Diagnóstica', 'Formativa', 'Somativa', 'Simulado')


class SubjectiveTest(db.Model):
    __tablename__ = 'subjective_tests'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    test_type = db.Column(db.String(50), default='Diagnóstica')
    subject_id = db.Column(db.String, db.ForeignKey('public.subject.id'), nullable=False)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('public.grade.id'), nullable=False)
    # Só para consulta/exibição — não dispara nenhuma regra (aplicação real é via escopo abaixo).
    application_date = db.Column(db.Date)

    # Escopo: mesmo padrão já usado em Test (município/escolas/turmas específicas).
    municipalities = db.Column(JSON)
    schools = db.Column(JSON)
    classes = db.Column(JSON)

    status = db.Column(db.String(20), default='pendente')  # pendente, em_correcao, concluida
    created_by = db.Column(db.String, db.ForeignKey('public.users.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))

    # Uso interno (ver docstring do módulo) — nunca exposto para edição pelo frontend.
    shadow_test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'))

    subject_rel = db.relationship('Subject', foreign_keys=[subject_id])
    grade = db.relationship('Grade', foreign_keys=[grade_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    shadow_test = db.relationship('Test', foreign_keys=[shadow_test_id])

    @property
    def questions(self):
        """Questões (habilidades) da avaliação, ordenadas por número."""
        from app.exams.models.subjectiveQuestion import SubjectiveQuestion
        return (
            SubjectiveQuestion.query
            .filter_by(subjective_test_id=self.id)
            .order_by(SubjectiveQuestion.number)
            .all()
        )

    def __repr__(self):
        return f'<SubjectiveTest {self.id}: {self.title}>'
