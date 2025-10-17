"""Notification dispatching helpers."""
from typing import Iterable


class NotificationService:
    """Stub for email/SMS notifications."""

    def send_email(self, subject: str, body: str, recipients: Iterable[str]) -> None:
        """Placeholder email sender."""

        raise NotImplementedError("Email notifications not yet implemented")
