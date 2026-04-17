from app import db
import uuid


class StudentTestOlimpics(db.Model):
    __tablename__ = 'student_test_olimpics'

    __table_args__ = (
        db.UniqueConstraint('student_id', 'test_id', name='uq_student_test_olimpics_student_test'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=False)
    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'), nullable=False)
    status = db.Column(db.String, default='agendada')
    application = db.Column(db.Text, nullable=False)
    expiration = db.Column(db.Text, nullable=False)
    timezone = db.Column(db.String(50), nullable=True, comment='Timezone da aplicação da avaliação (ex: America/Sao_Paulo)')
