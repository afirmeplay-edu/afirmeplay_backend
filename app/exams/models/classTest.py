from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ClassTest(db.Model):
    __tablename__ = 'class_test'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tenant.class.id'))
    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'))
    status = db.Column(db.String, default='agendada')
    application = db.Column(db.Text, nullable=False)
    expiration = db.Column(db.Text, nullable=False)
    timezone = db.Column(db.String(50), nullable=True, comment='Timezone da aplicação da avaliação (ex: America/Sao_Paulo)')