# SocketIO event handlers for real-time communication

from flask_socketio import emit
from app import socketio


@socketio.on('connect')
def handle_connect():
    """Handle client connection to the dashboard."""
    print("Dashboard connected")
    emit('connected', {'message': 'Live feed active'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from the dashboard."""
    print("Dashboard disconnected")
