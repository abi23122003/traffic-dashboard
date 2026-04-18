#!/bin/bash

# Initialize SQLite database
echo "Initializing database..."
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized successfully')"

# Start the Flask-SocketIO app
echo "Starting Flask app on port 5000..."
python app.py
