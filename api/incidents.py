# API endpoints for incident management and querying

from flask import Blueprint, request, jsonify
from app import db, socketio
from models import Incident

incidents_bp = Blueprint('incidents', __name__)


@incidents_bp.route('', methods=['GET'])
def get_incidents():
    """Get all incidents ordered by newest first."""
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return jsonify([incident.to_dict() for incident in incidents]), 200


@incidents_bp.route('', methods=['POST'])
def create_incident():
    """Create a new incident and broadcast it to all connected clients."""
    data = request.get_json()
    
    # Validate required fields
    if not data or not all(field in data for field in ['title', 'severity', 'lat', 'lng']):
        return jsonify({'error': 'Missing required fields: title, severity, lat, lng'}), 400
    
    # Create incident
    incident = Incident(
        title=data['title'],
        severity=data['severity'],
        lat=data['lat'],
        lng=data['lng']
    )
    
    # Save to database
    db.session.add(incident)
    db.session.commit()
    
    # Emit SocketIO event to all connected clients
    socketio.emit('incident_update', incident.to_dict(), broadcast=True)
    
    return jsonify(incident.to_dict()), 201
