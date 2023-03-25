from __future__ import annotations

from email.encoders import encode_base64
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging import getLogger
from typing import Dict, List

from aiohttp import ClientSession
from aiosmtplib import SMTP
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPConnectTimeoutError,
    SMTPServerDisconnected,
)
from mautrix.util.logging import TraceLogger


class Email:
    def __init__(
        self,
        subject: str,
        text: str,
        recipients: List[str],
        attachments: List[str] = [],
        format: str = "html",
        encode_type: str = "utf-8",
    ) -> None:
        self.subject = subject
        self.text = MIMEText(text, format, encode_type)
        self.recipients = recipients
        self.attachments = attachments

    @property
    def message(self) -> MIMEMultipart:
        message = MIMEMultipart("alternative")
        message["Subject"] = self.subject
        message.attach(self.text)
        return message

    async def attach_files(self, message: MIMEMultipart) -> MIMEMultipart:
        """This function takes a MIMEMultipart object and attaches files to it

        Parameters
        ----------
        message : MIMEMultipart
            The message to be sent.

        Returns
        -------
            A MIMEMultipart object with the attachments attached.

        """

        async with ClientSession() as http_session:
            for file_url in self.attachments:
                part = MIMEBase("application", "octet-stream")
                resp = await http_session.get(file_url)
                part.set_payload(await resp.read())
                encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{file_url}"')
                message.attach(part)

        return message


class EmailClient:
    session: SMTP = None
    http_session: ClientSession = None

    servers: Dict[str, "EmailClient"] = {}
    log: TraceLogger = getLogger("menuflow.email_client")

    def __init__(
        self,
        server_id: str,
        host: str,
        port: str,
        username: str,
        password: str,
        start_tls: bool = True,
    ) -> None:
        self.server_id = server_id
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.start_tls = start_tls

    def _add_to_cache(self):
        self.servers[self.server_id] = self

    async def login(self):
        """It connects to the mail server and logs in"""
        self.session = SMTP(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            start_tls=self.start_tls,
        )

        try:
            await self.session.connect()
            await self.session.ehlo()
            self.log.debug(f"The connection to the mail server {self.server_id} was successful")
        except SMTPConnectTimeoutError as e:
            self.log.error(e)
        except SMTPAuthenticationError as e:
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

        if not self.session.is_connected:
            await self.login()

        # Checking if there are any attachments in the email object.
        # If there are, it will call the attach_files method.
        if email.attachments:
            message = await email.attach_files(email.message)
        else:
            message = email.message

        try:
            await self.session.sendmail(self.username, email.recipients, message.as_string())
        except SMTPServerDisconnected as disconnected_error:
            self.log.error(
                f"ERROR SENDING EMAIL - DISCONNECTED: {disconnected_error} - Trying again ..."
            )
            await self.login()
            await self.session.sendmail(self.username, email.recipients, message.as_string())
        except Exception as error:
            self.log.exception(f"ERROR SENDING EMAIL: {error}")

    @classmethod
    def get_by_server_id(cls, server_name: str) -> EmailClient:
        return cls.servers.get(server_name)
