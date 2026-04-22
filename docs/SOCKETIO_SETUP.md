# Socket.IO Real-Time Integration Guide

## Overview

This Traffic Dashboard implements real-time incident and officer status updates using **Socket.IO** with **Redis** as the message queue. The Police Supervisor Command Center receives live updates for:

- **New incidents** (`incident_new`)
- **Incident updates** (`incident_updated`) - when status changes (dispatched, resolved)
- **Officer status changes** (`officer_status_changed`) - when dispatched or returns

## Architecture

### Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| **FastAPI** | 0.100.0+ | Main web framework |
| **python-socketio** | 5.11.0+ | Async Socket.IO server |
| **Redis** | 7-alpine | Message queue for Socket.IO broadcasts |
| **socket.io.js** | 4.7.5+ | Browser client library (CDN) |

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Supervisor Dashboard (Browser)                                  │
│ - Connects to /police namespace via Socket.IO                   │
│ - Joins district room (auto-assigned from JWT)                 │
│ - Listens for incident_new, incident_updated,                 │
│   officer_status_changed events                                │
└─────────────────────────────────────────────────────────────────┘
              ▲                                    ▼
              │ Real-time events                   │ WebSocket
              │ (HTTP upgrade + polling fallback)  │ with credentials
              │                                    │
        ┌─────────────────────────────────────────────────────────┐
        │ FastAPI Backend (app.py)                                │
        │ - Socket.IO AsyncServer with /police namespace          │
        │ - Emits events on specific endpoints:                   │
        │   * POST /api/incident/new → incident_new              │
        │   * POST /api/dispatch → officer_status_changed        │
        │   * POST /api/incident/resolve → incident_updated      │
        └─────────────────────────────────────────────────────────┘
              ▼                                    ▲
              │ Publish events to Redis rooms     │ Subscribe
              │ room = district_id                │
              │                                    │
        ┌─────────────────────────────────────────────────────────┐
        │ Redis Server                                            │
        │ - Pub/Sub channels for Socket.IO                        │
        │ - Multi-process scaling support                         │
        └─────────────────────────────────────────────────────────┘
```

## Setup Instructions

### 1. System Requirements

- **Python 3.8+**
- **Redis 7+** (running on `localhost:6379` or `redis:6379` in Docker)
- **FastAPI 0.100.0+**
- **PostgreSQL 15+** (for incident/officer data)

### 2. Installation

All required packages are already in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages:
- `python-socketio>=5.11.0` - Socket.IO async server
- `redis>=4.5.0` - Redis client for pub/sub
- `Flask-SocketIO>=5.3.6` - Optional, for compatibility

### 3. Docker Compose Setup

The `docker-compose.yml` includes Redis service:

```yaml
redis:
  image: redis:7-alpine
  container_name: traffic_redis
  ports:
    - "6379:6379"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 5s
    retries: 5
```

To run with Docker:

```bash
docker-compose up -d
```

### 4. Environment Configuration

The app automatically configures Socket.IO Redis URL:

```bash
# In docker-compose.yml or .env
SOCKETIO_REDIS_URL=redis://redis:6379/0
```

For local development:

```bash
export SOCKETIO_REDIS_URL=redis://localhost:6379/0
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## Frontend Integration

### Socket.IO Connection

Located in `templates/police/supervisor_dashboard.html`:

```javascript
function connectCommandCenterSocket() {
    const commandCenterSocket = io('/police', {
        path: '/socket.io/',
        withCredentials: true,  // ← Send HttpOnly cookies
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 10,
    });

    // Authenticate and join district
    commandCenterSocket.on('connect', () => {
        commandCenterSocket.emit('join_district', { 
            district_id: supervisorDistrictId 
        });
    });
}
```

### Authentication

The Socket.IO connection uses **HttpOnly JWT cookies** for authentication:

1. **Client connects** with `withCredentials: true`
2. **Browser automatically sends** HttpOnly `token` or `access_token` cookie
3. **Backend validates JWT** in `socketio_events.py:authenticate_socket_user()`
4. **Authorization enforced** - requires `police_supervisor` or `police_officer` role

**Cookie requirements:**
- ✅ HttpOnly flag (not accessible to JavaScript)
- ✅ Secure flag (HTTPS only in production)
- ✅ SameSite=Strict or Lax (CSRF protection)
- ✅ Domain scoped to application domain

### Event Listeners

```javascript
// Listen for real-time updates
commandCenterSocket.on('incident_new', async (data) => {
    console.log('New incident:', data);
    await loadIncidentsFromApi();
    await loadOfficersFromApi();
});

commandCenterSocket.on('incident_updated', async (data) => {
    console.log('Incident updated:', data);
    // Re-fetch data to show latest state
});

commandCenterSocket.on('officer_status_changed', async (data) => {
    console.log('Officer status changed:', data);
    // Update patrol units display
});
```

## Backend Event Emission

### 1. Incident Creation

**Endpoint:** `POST /api/incident/new`

```python
# In app.py
await emit_incident_new(
    sio,
    district_id,
    incident_record,
    actor=current_user.get("username", "Unknown Supervisor"),
)
```

**Event payload:**
```json
{
    "district_id": "district_1",
    "incident": {
        "id": "incident-abc123",
        "type": "traffic",
        "severity": "high",
        "description": "Multi-vehicle accident",
        "latitude": 13.0827,
        "longitude": 80.2707
    },
    "actor": "supervisor_name",
    "timestamp": "2024-04-18T10:30:45.123Z"
}
```

### 2. Officer Dispatch

**Endpoint:** `POST /api/dispatch`

When an officer is assigned to an incident:

```python
# In app.py dispatch_patrol_unit()
await emit_officer_status_changed(
    sio,
    district_id,
    {
        "id": officer_id,
        "name": officer_name,
        "status": "dispatched",
        "incident_id": incident_id,
    },
    actor=supervisor_username,
)
```

**Event payload:**
```json
{
    "district_id": "district_1",
    "officer": {
        "id": "officer_123",
        "name": "Officer Smith",
        "status": "dispatched",
        "incident_id": "incident-abc123"
    },
    "actor": "supervisor_name",
    "timestamp": "2024-04-18T10:31:20.456Z"
}
```

### 3. Incident Resolution

**Endpoint:** `POST /api/incident/resolve`

When incident is marked resolved:

```python
# In app.py resolve_incident()
await emit_incident_updated(
    sio,
    district_id,
    {"id": incident_id, "status": "resolved"},
    update_type="resolved",
    actor=supervisor_username,
)

# And when officer returns
await emit_officer_status_changed(
    sio,
    district_id,
    {
        "id": officer_id,
        "status": "available",
    },
    actor=supervisor_username,
)
```

## Security

### 1. JWT Authentication

- Token extracted from `token` or `access_token` HttpOnly cookie
- Validated with `SECRET_KEY` and `ALGORITHM` (HS256)
- Checked for `sub` (username) and `role` claims
- Must have role: `police_supervisor` or `police_officer`

### 2. Authorization

- **District Isolation:** Users can only receive events for their assigned district
- **Role-Based Access:** Only police roles can connect to `/police` namespace
- **Cookie Security:** Token is HttpOnly, cannot be accessed by JavaScript XSS

### 3. Session Management

```python
# socketio_events.py
user_claims = authenticate_socket_user(environ)
await sio.save_session(sid, user_claims, namespace=POLICE_NAMESPACE)

# Clients automatically assigned to their district room
if district_id:
    await sio.enter_room(sid, district_id, namespace=POLICE_NAMESPACE)
```

## Debugging

### Enable Socket.IO Logging

In `app.py`, enable debug mode:

```python
import logging
logging.getLogger('socketio').setLevel(logging.DEBUG)
logging.getLogger('engineio').setLevel(logging.DEBUG)
```

### Browser Console

Open browser DevTools (F12) and check:

1. **Network tab:**
   - WebSocket connection to `/socket.io/`
   - Cookies sent with request

2. **Console tab:**
   ```javascript
   // Check socket connection
   console.log(commandCenterSocket.connected);
   
   // Monitor events
   commandCenterSocket.on('*', (event, ...args) => {
       console.log('Event:', event, args);
   });
   ```

### Server Logs

```bash
# Check connection logs
docker logs traffic_dashboard | grep "Socket.IO"

# Output examples:
# ✅ Socket.IO police connected sid=abc123 user=supervisor1 district=district_1
# ⚠️ Socket.IO auth rejected: Missing access token
# ❌ Socket.IO police disconnected sid=abc123
```

### Redis Verification

```bash
# Verify Redis is running
redis-cli ping
# Output: PONG

# Monitor pub/sub messages
redis-cli SUBSCRIBE "*"

# Check connected clients
redis-cli CLIENT LIST | grep socketio
```

## Troubleshooting

### Connection Fails with 401 Unauthorized

**Problem:** Browser shows "Could not validate credentials"

**Cause:** HttpOnly cookie not sent with request

**Solution:**
1. Verify cookie is set: `document.cookie` should NOT show token (HttpOnly)
2. Check network tab: Request headers should include `Cookie: token=...`
3. Verify frontend has `withCredentials: true` in Socket.IO config
4. Check JWT hasn't expired: `exp` claim in token

### Connection Fails with 403 Forbidden

**Problem:** "Forbidden: police role required"

**Cause:** User role is not `police_supervisor` or `police_officer`

**Solution:**
1. Verify login credentials have police role
2. Check JWT `role` claim matches `POLICE_ROLES`
3. Test with admin account (may not have police role)

### Events Not Received

**Problem:** Dashboard doesn't update when incident created

**Cause:** 
- Socket.IO server not emitting events
- Redis pub/sub not working
- Client not listening to correct namespace/events

**Solution:**
1. Check server logs for emit errors
2. Verify Redis connection: `docker logs traffic_redis`
3. Monitor client events in browser console:
   ```javascript
   commandCenterSocket.onAny((event, ...args) => {
       console.log('Received:', event, args);
   });
   ```

### Connection Keeps Dropping

**Problem:** "Disconnected: io server disconnect"

**Cause:** 
- JWT token expired
- Redis connection lost
- Server restart

**Solution:**
1. Increase `reconnectionAttempts` in client config
2. Monitor JWT expiration time
3. Ensure Redis is running: `docker ps | grep redis`

## Performance Optimization

### Redis Persistence

For production, enable Redis persistence:

```yaml
# docker-compose.yml
redis:
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

### Scaling Multiple App Instances

With Redis, multiple app instances automatically share Socket.IO events:

```yaml
# docker-compose.yml - add multiple app services
app1:
  build: .
  environment:
    SOCKETIO_REDIS_URL: redis://redis:6379/0

app2:
  build: .
  environment:
    SOCKETIO_REDIS_URL: redis://redis:6379/0

app3:
  build: .
  environment:
    SOCKETIO_REDIS_URL: redis://redis:6379/0
```

All instances share the same Socket.IO Redis manager.

### Connection Pooling

Adjust uvicorn workers for better concurrency:

```bash
# In Dockerfile or run command
uvicorn app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop
```

## Testing

### Test Socket.IO Connection Locally

```bash
# 1. Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# 2. Start app
export SOCKETIO_REDIS_URL=redis://localhost:6379/0
python -m uvicorn app:app --reload

# 3. Login and test
# - Open http://localhost:8000/police/supervisor
# - Check browser console for connection
# - Create new incident: POST /api/incident/new
# - Should see real-time update on dashboard
```

### Unit Test Example

```python
# tests/test_socketio.py
import pytest
from socketio_events import authenticate_socket_user, POLICE_ROLES
from fastapi import HTTPException, status

def test_authenticate_missing_token():
    """Test auth fails without token"""
    environ = {"HTTP_COOKIE": ""}
    with pytest.raises(HTTPException) as exc:
        authenticate_socket_user(environ)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

def test_authenticate_invalid_role():
    """Test auth fails without police role"""
    # Mock JWT decode to return admin role
    environ = {"HTTP_COOKIE": "token=valid_jwt"}
    # Would fail if role not in POLICE_ROLES
```

## File Reference

| File | Purpose |
|------|---------|
| `app.py` | Main FastAPI app with Socket.IO setup and endpoints |
| `socketio_events.py` | Socket.IO handlers, authentication, event emission |
| `templates/police/supervisor_dashboard.html` | Frontend Socket.IO connection and listeners |
| `docker-compose.yml` | Redis service configuration |
| `requirements.txt` | Dependencies (python-socketio, redis) |

## Additional Resources

- [Socket.IO Docs](https://socket.io/docs/v4/)
- [python-socketio](https://python-socketio.readthedocs.io/)
- [Redis Pub/Sub](https://redis.io/docs/pub-sub/)
- [FastAPI + Socket.IO](https://socket.io/docs/v4/server-implementation/#fastapi)
- [JWT Authentication](https://python-jose.readthedocs.io/)

## Support

For issues or questions:

1. Check browser console for client-side errors
2. Review server logs: `docker logs traffic_dashboard`
3. Monitor Redis: `redis-cli MONITOR`
4. Enable debug logging in `logging_config.py`
