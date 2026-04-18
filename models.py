# Database models for incidents, officers, and other entities

from app import db
from datetime import datetime


class Incident(db.Model):
    """Model representing a police incident or emergency call."""
    __tablename__ = 'incidents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='medium')  # critical, high, medium, low
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')  # open, assigned, in-progress, closed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert incident to JSON-serializable dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'severity': self.severity,
            'lat': self.lat,
            'lng': self.lng,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Officer(db.Model):
    """Model representing a police officer with location and status tracking."""
    __tablename__ = 'officers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    badge = db.Column(db.String(50), nullable=False, unique=True)
    status = db.Column(db.String(20), nullable=False, default='available')  # available, en-route, occupied
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    skills = db.Column(db.String(500), nullable=True, default='')  # comma-separated skills
    last_ping = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        """Convert officer to JSON-serializable dictionary with skills as list."""
        skills_list = [s.strip() for s in self.skills.split(',') if s.strip()] if self.skills else []
        return {
            'id': self.id,
            'name': self.name,
            'badge': self.badge,
            'status': self.status,
            'lat': self.lat,
            'lng': self.lng,
            'skills': skills_list,
            'last_ping': self.last_ping.isoformat() if self.last_ping else None
        }
