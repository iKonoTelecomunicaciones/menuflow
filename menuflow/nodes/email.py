from typing import List

from ..email_client import Email as EmailMessage
from ..email_client import EmailClient
from ..repository import Email as EmailModel
from .message import Message


class Email(Message):

    email_client: EmailClient = None

    def __init__(self, email_node_data: EmailModel) -> None:
        Message.__init__(self, email_node_data)
        self.data = email_node_data

    @property
    def server_id(self) -> str:
        return self.render_data(self.data.get("server_id", ""))

    @property
    def subject(self) -> str:
        return self.render_data(self.data.get("subject", ""))

    @property
    def recipients(self) -> List[str]:
        return self.render_data(self.data.get("recipients", []))

    @property
    def attachments(self) -> List[str]:
        return self.render_data(self.data.get("attachments", []))

    @property
    def format(self) -> str:
        return self.render_data(self.data.get("format", ""))

    @property
    def encode_type(self) -> str:
        return self.render_data(self.data.get("encode_type", ""))

    async def run(self):

        if not self.email_client:
            self.email_client = EmailClient.get_by_server_id(self.server_id)

        self.log.debug(f"Sending email {self.subject or self.text} to {self.recipients}")

        email = EmailMessage(
            subject=self.subject,
            text=self.text,
            recipients=self.recipients,
            attachments=self.attachments,
            format=self.format,
            encode_type=self.encode_type,
        )
        await self.email_client.send_email(email=email)

        await self._update_node()
