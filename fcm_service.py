"""Firebase Cloud Messaging helper with safe fallback mode."""

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_firebase_ready = False


def _init_firebase() -> None:
    global _firebase_ready
    if _firebase_ready:
        return

    cred_path = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if not cred_path or not os.path.exists(cred_path):
        logger.warning("FCM fallback mode enabled: FIREBASE_CREDENTIALS_JSON is missing")
        return

    try:
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(cred_path))
        _firebase_ready = True
        logger.info("Firebase admin initialized")
    except Exception as exc:
        logger.warning("Firebase admin init failed, fallback mode enabled: %s", exc)


def send_dispatch_notification(
    officer_device_token: Optional[str],
    title: str,
    body: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Send push notification to a device token.

    If Firebase is not configured, this function logs and returns a mock result so
    dispatch flows still work in development.
    """
    if not officer_device_token:
        return {"sent": False, "reason": "missing_device_token"}

    _init_firebase()

    if not _firebase_ready:
        logger.info(
            "FCM mock send => token=%s payload=%s",
            officer_device_token[:10] + "...",
            json.dumps({"title": title, "body": body, "data": data}),
        )
        return {"sent": False, "reason": "firebase_not_configured", "mock": True}

    try:
        from firebase_admin import messaging

        msg = messaging.Message(
            token=officer_device_token,
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in data.items()},
        )
        message_id = messaging.send(msg)
        return {"sent": True, "message_id": message_id}
    except Exception as exc:
        logger.error("FCM send failed: %s", exc)
        return {"sent": False, "reason": str(exc)}
