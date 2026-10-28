"""FCM messaging adapter that degrades to a disabled provider."""

import asyncio
import json
import logging
from typing import Literal, Protocol

from app.core.config import get_settings

PushResult = Literal["sent", "unregistered", "failed", "disabled"]
logger = logging.getLogger("fetch.notifications")
_disabled_warning_emitted = False


class PushProvider(Protocol):
    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult: ...


class DisabledPushProvider:
    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult:
        return "disabled"


class FcmPushProvider:
    def __init__(self, credentials_json: str):
        try:
            import firebase_admin
            from firebase_admin import credentials

            info = json.loads(credentials_json)
            self._app = firebase_admin.initialize_app(
                credentials.Certificate(info), name=f"fetch-push-{id(self)}"
            )
        except (ImportError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("FCM credentials are invalid") from exc

    async def send(self, token: str, title: str, body: str, data: dict[str, str]) -> PushResult:
        def deliver() -> PushResult:
            from firebase_admin import messaging

            try:
                messaging.send(
                    messaging.Message(
                        token=token,
                        notification=messaging.Notification(title=title, body=body),
                        data=data,
                    ),
                    app=self._app,
                )
                return "sent"
            except Exception as exc:  # SDK exception hierarchy changes between releases.
                if exc.__class__.__name__ == "UnregisteredError":
                    return "unregistered"
                logger.warning("push_delivery_failed")
                return "failed"

        return await asyncio.to_thread(deliver)


def push_provider() -> PushProvider:
    global _disabled_warning_emitted
    credentials_json = get_settings().fcm_credentials_json
    if not credentials_json:
        if not _disabled_warning_emitted:
            logger.warning("push_disabled_missing_credentials")
            _disabled_warning_emitted = True
        return DisabledPushProvider()
    try:
        return FcmPushProvider(credentials_json)
    except RuntimeError:
        if not _disabled_warning_emitted:
            logger.warning("push_disabled_invalid_credentials")
            _disabled_warning_emitted = True
        return DisabledPushProvider()
