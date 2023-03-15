from typing import List

from ..email_client import Email as EmailMessage
from ..email_client import EmailClient
from ..repository import Email as EmailModel
from .message import Message


class Email(Message):
    def __init__(self, email_node_data: EmailModel) -> None:
        Message.__init__(email_node_data)
        self.data = email_node_data
        self.email_client = EmailClient.get_by_server_id(self.server_id)

    @property
    def server_id(self) -> str:
        return self.render_data(self.data.get("server_id", ""))

    @property
    def sender(self) -> str:
        return self.render_data(self.data.get("sender", ""))

    @property
    def subject(self) -> str:
        return self.render_data(self.data.get("subject", ""))

    @property
    def recipients(self) -> List[str]:
        return self.render_data(self.data.get("recipients", []))

    @property
    def format(self) -> str:
        return self.render_data(self.data.get("format", ""))

    @property
    def encode_type(self) -> str:
        return self.render_data(self.data.get("encode_type", ""))

    async def run(self):
        email = EmailMessage(
            sender=self.sender,
            subject=self.subject,
            text=self.text,
            recipients=self.recipients,
            format=self.format,
            encode_type=self.encode_type,
        )
        await self.email_client.send_email(email=email)
