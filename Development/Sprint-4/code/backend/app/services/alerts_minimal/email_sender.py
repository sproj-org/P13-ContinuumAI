"""SMTP sender for minimal alert notifications."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage


class EmailSender:
    """Simple SMTP wrapper for sending text emails."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        from_address: str,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_address = from_address

    def send(self, *, to_addresses: list[str], subject: str, body: str) -> None:
        if not to_addresses:
            raise ValueError("At least one recipient is required")

        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = ", ".join(to_addresses)
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=20) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(message)
