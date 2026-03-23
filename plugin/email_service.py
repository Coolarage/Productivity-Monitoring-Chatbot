from __future__ import annotations

from abc import ABC, abstractmethod
import smtplib
import ssl
from email.message import EmailMessage
from typing import List

from .schemas import EmailNotification


class EmailSender(ABC):
    """
    Abstraction for sending emails.

    The host system can provide its own implementation (SMTP, SendGrid, etc.)
    by implementing this interface and wiring it into the plugin.
    """

    @abstractmethod
    def send_email(self, email: EmailNotification) -> None:
        ...

    def send_bulk(self, emails: List[EmailNotification]) -> None:
        for e in emails:
            self.send_email(e)


class ConsoleEmailSender(EmailSender):
    """
    Demo implementation that just prints emails to the console.
    Suitable for thesis demonstrations and local testing.
    """

    def send_email(self, email: EmailNotification) -> None:
        print("\n--- Email Notification ---")
        print(f"To: {email.to}")
        print(f"Subject: {email.subject}")
        print("Body:")
        print(email.body)
        print("--- End Email ---\n")


class SmtpEmailSender(EmailSender):
    """
    Real SMTP implementation using a Gmail-compatible server.

    This demo version uses hard-coded dummy values which you MUST replace
    with your own test credentials before using. Do not commit real
    credentials to version control.
    """

    def __init__(self) -> None:
        # TODO: replace these dummy values with your own test account
        # details (e.g. a Gmail app password) for local testing only.
        self.host = "smtp.gmail.com"
        self.port = 587
        self.username = "adham.elsegeeny@gmail.com"
        self.password = "fwobpvxykndlosig"
        self.from_email = "adham.elsegeeny@example.com"
        self.from_name = "Productivity Assistant (Demo)"

    def send_email(self, email: EmailNotification) -> None:
        msg = EmailMessage()
        if self.from_name:
            msg["From"] = f"{self.from_name} <{self.from_email}>"
        else:
            msg["From"] = self.from_email
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.body)

        context = ssl.create_default_context()
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls(context=context)
            server.login(self.username, self.password)
            server.send_message(msg)

