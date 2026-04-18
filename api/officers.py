# API endpoints for officer management and status tracking

from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db, socketio
from models import Officer

officers_bp = Blueprint('officers', __name__)


@officers_bp.route('/status', methods=['GET'])
def get_officers_status():
    """Get all officers with their current status."""
    officers = Officer.query.all()
    return jsonify([officer.to_dict() for officer in officers]), 200


@officers_bp.route('/dispatch', methods=['POST'])
def dispatch_officer():
    """Dispatch an officer to an incident."""
    data = request.get_json()
    
    # Validate required fields
    if not data or not all(field in data for field in ['officer_id', 'incident_id']):
        return jsonify({'error': 'Missing required fields: officer_id, incident_id'}), 400
    
    # Find officer by id
    officer = Officer.query.get(data['officer_id'])
    if not officer:
        return jsonify({'error': 'Officer not found'}), 404
    
    # Update officer status and last ping
    officer.status = 'en-route'
    officer.last_ping = datetime.utcnow()
    
    # Save to database
    db.session.commit()
    
    # Emit SocketIO event to all connected clients
    socketio.emit('officer_update', officer.to_dict(), broadcast=True)
    
    return jsonify({
        'message': 'Officer dispatched successfully',
        'officer': officer.to_dict()
    }), 200
