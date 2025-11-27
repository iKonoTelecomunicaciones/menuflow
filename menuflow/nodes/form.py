from typing import Any

from markdown import markdown
from mautrix.types import Format, MessageEvent, MessageType, TextMessageEventContent

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Form, FormMessage, FormMessageContent
from ..room import Room
from ..utils import Nodes, NodeStatus, Util
from .input import Input


class FormInput(Input):
    def __init__(self, form_node_data: Form, room: Room, default_variables: dict) -> None:
        Input.__init__(self, form_node_data, room, default_variables)
        self.content = form_node_data

    @property
    def template_name(self) -> dict[str, Any]:
        return self.render_data(self.content.get("template_name", ""))

    @property
    def language(self) -> str:
        return self.render_data(self.content.get("language", "en"))

    @property
    def body_variables(self) -> list[str]:
        return self.render_data(self.content.get("body_variables", []))

    @property
    def header_variables(self) -> dict[str, Any]:
        return self.render_data(self.content.get("header_variables", []))

    @property
    def button_variables(self) -> dict[str, Any]:
        return self.render_data(self.content.get("button_variables", []))

    @property
    def flow_action(self) -> dict[str, str | list | dict]:
        return self.render_data(self.content.get("flow_action", []))

    @property
    def form_message_content(self) -> FormMessage:
        form_message = FormMessage(
            msgtype="m.form",
            form_message=FormMessageContent(
                template_name=self.template_name,
                language=self.language,
                body_variables=self.body_variables,
                header_variables=self.header_variables,
                button_variables=self.button_variables,
                flow_action=self.flow_action,
            ),
        )
        form_message.trim_reply_fallback()
        return form_message

    async def __update_menu(self, case_id: str) -> str:
        o_connection = await self.get_case_by_id(case_id)
        await self.room.update_menu(o_connection)
        return o_connection

    async def check_fail_attempts(self):
        if not self.validation_attempts:
            return

        case_to_be_used = await self.manage_attempts()
        await self.room.route.update_node_vars()
        if case_to_be_used == NodeStatus.ATTEMPT_EXCEEDED.value:
            await self.__update_menu(case_to_be_used)
            return case_to_be_used

        if self.validation_fail_message:
            msg_content = TextMessageEventContent(
                msgtype=MessageType.TEXT,
                body=self.validation_fail_message,
                format=Format.HTML,
                formatted_body=markdown(text=self.validation_fail_message, extensions=["nl2br"]),
            )
            await self.send_message(self.room.room_id, msg_content)

    async def run(self, evt: MessageEvent | None):
        """Send WhhatApp flow and capture the response of it and save it as variables.
        if the MessageEvent is not m.form_response, wait for the user to send the response.

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object.
        evt : MessageEvent | None
            The event that triggered the node.

        """

        inactivity = self.inactivity_options

        if self.room.route.state == RouteState.INPUT:
            _variable = self.variable
            if not evt or not _variable or evt.content.msgtype != "m.form_response":
                self.log.warning(
                    f"[{self.room.room_id}] A problem occurred getting user response, message type is not m.form_response"
                )
                o_connection = await self.check_fail_attempts()

                if inactivity.get("active") and not o_connection:
                    await self.timeout_active_chats(inactivity)
                return

            await self.room.set_variable(_variable, evt.content.get("form_data"))
            o_connection = await self.__update_menu("submitted")

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeInputData,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_id=self.id,
                o_connection=o_connection,
                variables=self.room.all_variables | self.default_variables,
                conversation_uuid=await self.room.get_variable("room.conversation_uuid"),
            )
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"[{self.room.room_id}] Entering form input node {self.id}")
            await self.room.matrix_client.send_message_event(
                room_id=self.room.room_id,
                event_type="m.room.message",
                content=self.form_message_content,
            )
            await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.media,
                node_id=self.id,
                o_connection=None,
                variables=self.room.all_variables | self.default_variables,
                conversation_uuid=await self.room.get_variable("room.conversation_uuid"),
            )

            if inactivity.get("active") and not Util.get_tasks_by_name(
                task_name=self.room.room_id
            ):
                await self.timeout_active_chats(inactivity)
