from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime


class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    iframeHtml = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.String(500), nullable=True)
    author = db.Column(db.String(200), nullable=True)
    provider = db.Column(db.String(50), nullable=False, default='wordwall')
    subject = db.Column(db.String(100), nullable=False)
    userId = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    createdAt = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updatedAt = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relacionamentos
    user = db.relationship("User", backref="games")
    game_classes = db.relationship('GameClass', back_populates='game', cascade='all, delete-orphan')
    
    @property
    def classes(self):
        """Retorna as turmas associadas ao jogo"""
        return [gc.class_ for gc in self.game_classes]


class GameClass(db.Model):
    __tablename__ = 'game_classes'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id = db.Column(db.String, db.ForeignKey('games.id'), nullable=False)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('class.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    game = db.relationship('Game', back_populates='game_classes')
    class_ = db.relationship('Class')
    
    def __repr__(self):
        return f'<GameClass {self.game_id} - {self.class_id}>' 