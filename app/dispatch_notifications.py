"""Dispatch notification service for push notifications and SocketIO events."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from .fcm_service import send_dispatch_notification

logger = logging.getLogger(__name__)


def send_officer_dispatch_notification(
    officer_device_token: Optional[str],
    officer_id: str,
    incident_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send dispatch notification to officer's mobile device via FCM.
    
    Sends a push notification when an officer is dispatched to an incident.
    If the officer has a registered mobile device token, the notification will
    be delivered via Firebase Cloud Messaging.
    
    Args:
        officer_device_token: Firebase device token for the officer's mobile app
        officer_id: Officer/unit ID being dispatched
        incident_data: Incident details including title, severity, location info
                      Expected keys: id, title, severity, lat, lng, notes
    
    Returns:
        Dict with notification status:
        - If sent: {"sent": True, "message_id": "<id>"}
        - If failed/skipped: {"sent": False, "reason": "<reason>", ...}
        - Mock mode: {"sent": False, "reason": "firebase_not_configured", "mock": True}
    
    Example:
        result = send_officer_dispatch_notification(
            "device_token_xyz",
            "unit_001",
            {
                "id": "incident_123",
                "title": "Traffic Accident",
                "severity": "high",
                "lat": 40.7128,
                "lng": -74.0060,
                "notes": "2-vehicle collision"
            }
        )
    """
    if not officer_device_token:
        logger.debug(f"Dispatch notification skipped for officer {officer_id}: no device token")
        return {"sent": False, "reason": "missing_device_token"}
    
    incident_id = incident_data.get("id", "unknown")
    incident_title = incident_data.get("title", "New Incident")
    severity = incident_data.get("severity", "medium").upper()
    
    # Construct notification title and body
    title = f"Dispatch - {severity}"
    body = f"{incident_title} (ID: {incident_id})"
    
    # Construct data payload for the app to handle the dispatch
    data_payload = {
        "incident_id": str(incident_data.get("id", "")),
        "incident_title": incident_title,
        "severity": str(incident_data.get("severity", "medium")),
        "latitude": str(incident_data.get("lat", "")),
        "longitude": str(incident_data.get("lng", "")),
        "notes": str(incident_data.get("notes", "")),
        "dispatched_at": datetime.now(UTC).isoformat(),
    }
    
    # Send via FCM
    result = send_dispatch_notification(
        officer_device_token,
        title=title,
        body=body,
        data=data_payload,
    )
    
    # Log the outcome
    if result.get("sent"):
        logger.info(
            f"✅ Dispatch notification sent to officer {officer_id}: "
            f"incident {incident_id}, message_id={result.get('message_id')}"
        )
    else:
        reason = result.get("reason", "unknown_error")
        is_mock = result.get("mock", False)
        log_level = logging.DEBUG if is_mock else logging.WARNING
        logger.log(
            log_level,
            f"❌ Dispatch notification failed for officer {officer_id} "
            f"(incident {incident_id}): {reason}"
        )
    
    return result
