import uuid

from app import db


class UserSettings(db.Model):
    __tablename__ = 'user_settings'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False, unique=True)
    theme = db.Column(db.String(50), nullable=True)
    font_family = db.Column(db.String(100), nullable=True)
    font_size = db.Column(db.Integer, nullable=True)
    sidebar_theme_id = db.Column(db.String(128), nullable=True)
    frame_id = db.Column(db.String(128), nullable=True)
    stamp_id = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())

    user = db.relationship(
        'User',
        backref=db.backref('user_settings', uselist=False, cascade='all, delete-orphan')
    )


    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'theme': self.theme,
            'font_family': self.font_family,
            'font_size': self.font_size,
            'sidebar_theme_id': self.sidebar_theme_id,
            'frame_id': self.frame_id,
            'stamp_id': self.stamp_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

