from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

class PlayTvVideo(db.Model):
    __tablename__ = 'play_tv_videos'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = db.Column(db.String, nullable=False)
    title = db.Column(db.String(100), nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'), nullable=False)
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'), nullable=False)
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    grade = db.relationship('Grade', foreign_keys=[grade_id])
    subject = db.relationship('Subject', foreign_keys=[subject_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    video_schools = db.relationship('PlayTvVideoSchool', back_populates='video', cascade='all, delete-orphan')
    video_classes = db.relationship('PlayTvVideoClass', back_populates='video', cascade='all, delete-orphan')
    
    @property
    def schools(self):
        """Retorna as escolas associadas ao vídeo"""
        return [vs.school for vs in self.video_schools]
    
    @property
    def classes(self):
        """Retorna as classes associadas ao vídeo"""
        return [vc.class_ for vc in self.video_classes]

class PlayTvVideoSchool(db.Model):
    __tablename__ = 'play_tv_video_schools'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = db.Column(db.String, db.ForeignKey('play_tv_videos.id'), nullable=False)
    school_id = db.Column(db.String, db.ForeignKey('school.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    video = db.relationship('PlayTvVideo', back_populates='video_schools')
    school = db.relationship('School')
    
    def __repr__(self):
        return f'<PlayTvVideoSchool {self.video_id} - {self.school_id}>'

class PlayTvVideoClass(db.Model):
    __tablename__ = 'play_tv_video_classes'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = db.Column(db.String, db.ForeignKey('play_tv_videos.id'), nullable=False)
    class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    video = db.relationship('PlayTvVideo', back_populates='video_classes')
    class_ = db.relationship('Class')
    
    def __repr__(self):
        return f'<PlayTvVideoClass {self.video_id} - {self.class_id}>'



