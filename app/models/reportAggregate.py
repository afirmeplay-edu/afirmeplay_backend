from datetime import datetime
import uuid

from app import db


class ReportAggregate(db.Model):
    __tablename__ = 'report_aggregates'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'), nullable=False, index=True)
    scope_type = db.Column(db.String(32), nullable=False, index=True)
    scope_id = db.Column(db.String, nullable=True, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    student_count = db.Column(db.Integer, nullable=False, default=0)
    
    # Análise de IA (cacheada separadamente)
    ai_analysis = db.Column(db.JSON, nullable=True, default=dict)
    ai_analysis_generated_at = db.Column(db.DateTime, nullable=True)
    ai_analysis_is_dirty = db.Column(db.Boolean, nullable=False, default=False)
    
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    is_dirty = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint('test_id', 'scope_type', 'scope_id', name='uq_report_aggregate_scope'),
        {"schema": "tenant"},
    )

    def mark_dirty(self):
        self.is_dirty = True
        self.updated_at = datetime.utcnow()
    
    def mark_ai_dirty(self):
        """Marca análise de IA como desatualizada"""
        self.ai_analysis_is_dirty = True
        self.updated_at = datetime.utcnow()

    def update_payload(self, payload: dict, student_count: int):
        self.payload = payload or {}
        self.student_count = student_count
        self.generated_at = datetime.utcnow()
        self.is_dirty = False
        self.updated_at = datetime.utcnow()
    
    def update_ai_analysis(self, ai_analysis: dict):
        """Atualiza análise de IA"""
        self.ai_analysis = ai_analysis or {}
        self.ai_analysis_generated_at = datetime.utcnow()
        self.ai_analysis_is_dirty = False
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            "id": self.id,
            "test_id": self.test_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "payload": self.payload,
            "ai_analysis": self.ai_analysis,
            "student_count": self.student_count,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "ai_analysis_generated_at": self.ai_analysis_generated_at.isoformat() if self.ai_analysis_generated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_dirty": self.is_dirty,
            "ai_analysis_is_dirty": self.ai_analysis_is_dirty,
        }



