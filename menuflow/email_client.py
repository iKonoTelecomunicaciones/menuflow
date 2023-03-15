from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import getLogger
from typing import Dict, List

from aiosmtplib import SMTP
from aiosmtplib.errors import SMTPConnectTimeoutError, SMTPServerDisconnected
from mautrix.util.logging import TraceLogger


class Email:
    def __init__(
        self,
        sender: str,
        subject: str,
        text: str,
        recipients: List[str],
        format: str = "html",
        encode_type: str = "utf-8",
    ) -> None:
        self.sender = sender
        self.subject = subject
        self.text = MIMEText(text, format, encode_type)
        self.recipients = recipients

    @property
    def message(self) -> MIMEMultipart:
        message = MIMEMultipart("alternative")
        message["Subject"] = self.subject
        message.attach(self.text)
        return message


class EmailClient:
    session: SMTP = None

    servers: Dict[str, "EmailClient"]
    log: TraceLogger = getLogger("menuflow.email_client")

    def __init__(
        self,
        server_id: str,
        host: str,
        port: str,
        username: str,
        password: str,
        use_tls: bool = False,
        start_tls: bool = False,
    ) -> None:
        self.server_id = server_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.start_tls = start_tls

    def _add_to_cache(self):
        self.servers[self.server_id] = self

    async def login(self):
        self.session = SMTP(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            use_tls=self.use_tls,
            start_tls=self.start_tls,
        )

        try:
            await self.session.connect()
            self.log.debug(f"The connection to the mail server {self.server_id} was successful")
        except SMTPConnectTimeoutError as e:
            self.log.error(e)
        except Exception as e:
            self.log.exception(e)

    async def send_email(self, email: Email):
        """If the email fails to send, log the error and try again

        Parameters
        ----------
        email : Email
            Email - This is the email object that we created earlier.

        """
        try:
            await self.session.sendmail(email.sender, email.recipients, email.message)
        except SMTPServerDisconnected as disconnected_error:
            self.log.error(
                f"ERROR SENDING EMAIL - DISCONNECTED: {disconnected_error} - Trying again ..."
            )
            await self.session.sendmail(email.sender, email.recipients, email.message)
        except Exception as error:
            self.log.exception(f"ERROR SENDING EMAIL: {error}")
            self.logout()

    def logout(self):
        self.log.warning(f"Closing email server conection [{self.host}] ...")
        self.session.close()

    @classmethod
    def get_by_server_id(cls, server_name: str) -> EmailClient:
        return cls.servers.get(server_name)
