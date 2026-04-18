#!/bin/bash

# Test curl command to POST a sample critical incident
# Make sure the Flask app is running on port 5000 before running this

echo "Sending test critical incident to the command center..."
curl -X POST http://localhost:5000/api/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Active Shooter - Downtown Plaza",
    "severity": "critical",
    "lat": 40.7128,
    "lng": -74.0060
  }' \
  -v

echo ""
echo "Test incident sent! Check the dashboard for real-time updates."
