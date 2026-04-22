# Socket.IO Quick Reference

## Quick Start (Development)

```bash
# 1. Ensure Redis is running
docker run -d -p 6379:6379 redis:7-alpine

# 2. Start backend with Socket.IO
export SOCKETIO_REDIS_URL=redis://localhost:6379/0
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

# 3. Open police supervisor dashboard
# Navigate to: http://localhost:8000/police/supervisor

# 4. Test real-time updates
# Create new incident via UI, check if dashboard updates without refresh
```

## Quick API Reference

### Emit Incident New
- **Endpoint:** `POST /api/incident/new`
- **Event:** `incident_new`
- **Broadcast:** To all supervisors in district

```bash
curl -X POST http://localhost:8000/api/incident/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "incident_type": "traffic",
    "severity": "high",
    "description": "Multi-vehicle accident",
    "latitude": 13.0827,
    "longitude": 80.2707
  }'
```

### Dispatch Officer
- **Endpoint:** `POST /api/dispatch`
- **Events:** `incident_updated` + `officer_status_changed`
- **Broadcast:** To district room

```bash
curl -X POST http://localhost:8000/api/dispatch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "incident_id": "incident-123",
    "officer_id": "officer_456"
  }'
```

### Resolve Incident
- **Endpoint:** `POST /api/incident/resolve`
- **Events:** `incident_updated` + `officer_status_changed`
- **Broadcast:** To district room

```bash
curl -X POST http://localhost:8000/api/incident/resolve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "incident_id": "incident-123",
    "severity": "high",
    "incident_type": "traffic",
    "zone": "Zone A",
    "response_time_minutes": 5.5,
    "outcome": "resolved"
  }'
```

## Browser DevTools Tricks

### Monitor All Socket.IO Events
```javascript
// Paste into browser console
commandCenterSocket.onAny((event, ...args) => {
    console.log(`%c${event}`, 'color: #00ff00; font-weight: bold;', args[0]);
});
```

### Check Connection Status
```javascript
// In console
console.log('Connected:', commandCenterSocket.connected);
console.log('Socket ID:', commandCenterSocket.id);
console.log('Namespace:', commandCenterSocket.nsp);
```

### Manually Emit Event (for testing)
```javascript
// Emit join_district manually
commandCenterSocket.emit('join_district', { district_id: 'district_1' });
```

### Emit Test Event from Server (Flask-style)
```python
# In Python shell/test
from app import sio, emit_incident_new
import asyncio

asyncio.run(emit_incident_new(
    sio, 
    "district_1",
    {"id": "test-123", "severity": "high"},
    actor="test"
))
```

## Namespace & Room Structure

```
Socket.IO Server
├── /police (namespace)
│   ├── district_1 (room)
│   │   └── supervisor1, supervisor2, officer1
│   ├── district_2 (room)
│   │   └── supervisor3, officer2
│   └── district_3 (room)
│       └── supervisor4
```

**Broadcasting:**
```python
# Send to specific district (room)
await sio.emit('incident_new', data, room='district_1', namespace='/police')

# Send to all in namespace (not typically used)
await sio.emit('incident_new', data, namespace='/police')
```

## Common Issues Checklist

- [ ] Redis is running: `redis-cli ping` returns PONG
- [ ] Backend logs show "Socket.IO connected": check logs for "Socket.IO police connected"
- [ ] Browser Network tab shows WebSocket upgrade to `/socket.io/`
- [ ] JWT cookie is HttpOnly: `document.cookie` does NOT show token
- [ ] CORS allows Socket.IO: `allow_origins: ["*"]` in CORSMiddleware
- [ ] Firewall allows WebSocket: port 8000 accessible
- [ ] Token hasn't expired: Check JWT `exp` field
- [ ] User has police role: Token `role` is "police_supervisor" or "police_officer"
- [ ] Environment variable set: `SOCKETIO_REDIS_URL` points to Redis
- [ ] Frontend includes Socket.IO library: `<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>`

## Performance Tuning

### Reduce Event Frequency
```python
# Instead of refreshing full data on every event:
# Option 1: Batch updates (refresh every 2 seconds max)
# Option 2: Partial updates (only refresh changed sections)
# Option 3: Delta updates (send only changed fields)
```

### Optimize Redis
```bash
# Monitor Redis memory
redis-cli INFO memory

# Check pub/sub channels
redis-cli PUBSUB CHANNELS

# Monitor Socket.IO messages
redis-cli --stat
```

### Connection Pool
```python
# In app.py (FastAPI)
socket_client_manager = socketio.AsyncRedisManager(
    SOCKETIO_REDIS_URL,
    write_only=True  # For read-heavy workloads
)
```

## Docker-Compose Scaling

```yaml
version: '3.8'
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    
  app1:
    build: .
    ports:
      - "8001:8000"
    environment:
      SOCKETIO_REDIS_URL: redis://redis:6379/0
    
  app2:
    build: .
    ports:
      - "8002:8000"
    environment:
      SOCKETIO_REDIS_URL: redis://redis:6379/0
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    # Configure to load-balance between app1, app2
```

## Environment Variables

```bash
# Required
SOCKETIO_REDIS_URL=redis://localhost:6379/0

# Optional tuning
SOCKETIO_PING_INTERVAL=25
SOCKETIO_PING_TIMEOUT=60
SOCKETIO_MAX_CONNECTIONS=10000
```

## Log Levels

```python
# In logging_config.py or start script
import logging

logging.getLogger('socketio').setLevel(logging.DEBUG)  # Verbose
logging.getLogger('engineio').setLevel(logging.DEBUG)
logging.getLogger('app').setLevel(logging.INFO)
```

## Production Checklist

- [ ] Redis is running in production environment
- [ ] Redis persistence enabled (`--appendonly yes`)
- [ ] Socket.IO CORS configured for your domain
- [ ] JWT tokens signed with production SECRET_KEY
- [ ] HTTPS enabled (Socket.IO works over secure WebSockets)
- [ ] Firewall allows WebSocket connections
- [ ] Connection limits configured
- [ ] Monitoring/alerting for Redis and Socket.IO
- [ ] Rate limiting in place for sensitive endpoints
- [ ] Session cleanup for disconnected clients

## See Also

- Main docs: [SOCKETIO_SETUP.md](SOCKETIO_SETUP.md)
- Architecture: [app.py](app.py#L82-L98)
- Event handlers: [socketio_events.py](socketio_events.py)
- Frontend: [templates/police/supervisor_dashboard.html](templates/police/supervisor_dashboard.html#L2042)
