from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from mautrix.types import (
    LocationMessageEventContent,
    MediaMessageEventContent,
    MessageEvent,
    MessageType,
)

from ..db.route import RouteState
from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..inactivity_handler import InactivityHandler
from ..repository import Input as InputModel
from ..room import Room
from ..utils import Middlewares, Nodes, Util
from .message import Message
from .switch import Switch

if TYPE_CHECKING:
    from ..middlewares import ASRMiddleware, IRMMiddleware, LLMMiddleware, TTMMiddleware


class Input(Switch, Message):
    def __init__(self, input_node_data: InputModel, room: Room, default_variables: Dict) -> None:
        Switch.__init__(self, input_node_data, room=room, default_variables=default_variables)
        Message.__init__(self, input_node_data, room=room, default_variables=default_variables)
        self.content = input_node_data
        self.middlewares: Optional[
            List[LLMMiddleware, ASRMiddleware, IRMMiddleware, TTMMiddleware]
        ] = []

    @property
    def variable(self) -> str:
        return self.render_data(self.content.get("variable", ""))

    @property
    def input_type(self) -> MessageType:
        return MessageType(self.render_data(self.content.get("input_type", "m.text")))

    @property
    def inactivity_options(self) -> Dict[str, Any]:
        return self.content.get("inactivity_options", {})

    async def _set_input_content(
        self, content: MediaMessageEventContent | LocationMessageEventContent
    ) -> str:
        if self.input_type == content.msgtype:
            input_content = (
                content.serialize()
                if isinstance(content, MediaMessageEventContent)
                else Util.extract_location_info(content)
            )
            await self.room.set_variable(self.variable, input_content)
            return await self.get_case_by_id(True)
        else:
            return await self.get_case_by_id(False)

    async def input_media(self, content: MediaMessageEventContent):
        o_connection = await self._set_input_content(content)
        await self.room.update_menu(o_connection or "default")
        return o_connection

    async def input_location(self, content: LocationMessageEventContent):
        o_connection = await self._set_input_content(content)
        await self.room.update_menu(o_connection or "default")
        return o_connection

    async def input_text(self, text: str, middlewares_sorted: Dict[Middlewares, Any] = None):
        """It takes the input from the user and sets the variable to the input

        Parameters
        ----------
        content : MessageEventContent
            The content of the message event.

        """

        if self.middlewares:
            given_text = text
            if Middlewares.TTM in middlewares_sorted:
                _, given_text = await middlewares_sorted[Middlewares.TTM].run(text=text)

            if Middlewares.LLM in middlewares_sorted:
                await middlewares_sorted[Middlewares.LLM].run(text=given_text)
        else:
            try:
                if vars := self.set_variables:
                    await self.load_variables(vars)
                else:
                    await self.room.set_variable(
                        self.variable,
                        int(text) if text.isdigit() else text,
                    )
            except ValueError as e:
                self.log.warning(e)

        # If the node has an output connection, then update the menu to the output connection.
        # Otherwise, run the node and update the menu to the output connection.
        return await Switch.run(self, generate_event=False)

    async def run(self, evt: Optional[MessageEvent]):
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """

        middlewares_sorted = {
            Middlewares(middleware.type): middleware for middleware in self.middlewares
        }

        if self.room.route.state == RouteState.INPUT:
            if not evt:
                self.log.warning("A problem occurred getting message event.")
                return

            if self.input_type == MessageType.TEXT:
                self.room.set_node_var(content=evt.content.body)

                o_connection = await self.input_text(
                    text=evt.content.body, middlewares_sorted=middlewares_sorted
                )
            elif self.input_type == MessageType.IMAGE:
                if (
                    self.input_type == evt.content.msgtype
                    and Middlewares.IRM in middlewares_sorted
                ):
                    await middlewares_sorted[Middlewares.IRM].run(
                        image_mxc=evt.content.url,
                        content_type=evt.content.info.mimetype,
                        filename=evt.content.body,
                    )
                    o_connection = await Switch.run(self, generate_event=False)
                else:
                    o_connection = await self.input_media(content=evt.content)
            elif self.input_type == MessageType.AUDIO:
                if (
                    Middlewares.ASR in middlewares_sorted
                    and evt.content.msgtype == MessageType.AUDIO
                ):
                    audio_name = evt.content.file or "audio.ogg"
                    _, given_text = await middlewares_sorted[Middlewares.ASR].run(
                        audio_url=evt.content.url, audio_name=audio_name
                    )

                if Middlewares.LLM in middlewares_sorted:
                    await middlewares_sorted[Middlewares.LLM].run(text=given_text)

                if self.middlewares:
                    o_connection = await Switch.run(self=self, generate_event=False)
                else:
                    o_connection = await self.input_media(content=evt.content)
            elif self.input_type in [
                MessageType.FILE,
                MessageType.VIDEO,
            ]:
                o_connection = await self.input_media(content=evt.content)
            elif self.input_type == MessageType.LOCATION:
                o_connection = await self.input_location(content=evt.content)

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
            self.log.debug(f"Room {self.room.room_id} enters input node {self.id}")
            await Message.run(self, update_state=False, generate_event=False)

            self.room.set_node_var(content="")
            await self.room.update_menu(
                node_id=self.id, state=RouteState.INPUT, update_node_vars=False
            )

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.input,
                node_id=self.id,
                o_connection=None,
                variables=self.room.all_variables | self.default_variables,
                conversation_uuid=await self.room.get_variable("room.conversation_uuid"),
            )

            if (inactivity := self.inactivity_options) and not Util.get_tasks_by_name(
                task_name=self.room.room_id
            ):
                await self.timeout_active_chats(inactivity)

    async def timeout_active_chats(self, inactivity: dict):
        """It sends messages in time intervals to communicate customer
        that not entered information to input option.

        Parameters
        ----------
        inactivity : dict
            The inactivity options.

        """
        if inactivity.get("chat_timeout") is None and inactivity.get("attempts") is None:
            return

        if inactivity.get("warning_message"):
            inactivity["warning_message"] = self.render_data(inactivity["warning_message"])

        inactivity_handler = InactivityHandler(room=self.room, inactivity=inactivity)
        try:
            metadata = {"bot_mxid": self.room.bot_mxid}
            await Util.create_task_by_metadata(
                inactivity_handler.start(), name=self.room.room_id, metadata=metadata
            )

            self.log.debug(f"INACTIVITY TRIES COMPLETED -> {self.room.room_id}")
            o_connection = await self.get_case_by_id("timeout")
            await self.room.update_menu(node_id=o_connection, state=None)

            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeInputTimeout,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_id=self.id,
                o_connection=o_connection,
                variables=self.room.all_variables | self.default_variables,
                conversation_uuid=await self.room.get_variable("room.conversation_uuid"),
            )
            return

        except asyncio.CancelledError:
            self.log.error(f"Inactivity handler cancelled for room: {self.room.room_id}")
        except Exception as e:
            self.log.error(f"Inactivity handler error for room: {self.room.room_id}: {e}")
        finally:
            await Util.cancel_task(task_name=f"inactivity_restored_{self.room.room_id}")
