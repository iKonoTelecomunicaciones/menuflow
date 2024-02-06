import asyncio
from typing import Dict, List

from ..email_client import Email as EmailMessage
from ..email_client import EmailClient
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Email as EmailModel
from ..room import Room
from ..utils import Nodes
from .message import Message


class Email(Message):
    email_client: EmailClient = None

    def __init__(self, email_node_data: EmailModel, room: Room, default_variables: Dict) -> None:
        Message.__init__(self, email_node_data, room=room, default_variables=default_variables)
        self.content = email_node_data

    @property
    def server_id(self) -> str:
        return self.render_data(self.content.get("server_id", ""))

    @property
    def subject(self) -> str:
        return self.render_data(self.content.get("subject", ""))

    @property
    def recipients(self) -> List[str]:
        return self.render_data(self.content.get("recipients", []))

    @property
    def attachments(self) -> List[str]:
        return self.render_data(self.content.get("attachments", []))

    @property
    def format(self) -> str:
        return self.render_data(self.content.get("format", ""))

    @property
    def encode_type(self) -> str:
        return self.render_data(self.content.get("encode_type", ""))

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

        asyncio.create_task(self.email_client.send_email(email=email))

        o_connection = await self.get_o_connection()
        await self._update_node(o_connection)

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeEntry,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.email,
            node_id=self.id,
            o_connection=o_connection,
            variables=self.room.all_variables | self.default_variables,
        )
