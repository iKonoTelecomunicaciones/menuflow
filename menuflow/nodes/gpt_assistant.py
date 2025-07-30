import html
import json
import mimetypes
import re
from asyncio import create_task, sleep
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import openai
from mautrix.types import MessageEvent, MessageType, RoomID
from mautrix.util.magic import mimetype

from ..db.route import RouteState
from ..repository import GPTAssistant as GPTAssistantModel
from ..room import Room
from ..utils import Middlewares, Util
from .switch import Switch

if TYPE_CHECKING:
    from ..middlewares import ASRMiddleware, TTMMiddleware


class GPTAssistant(Switch):
    assistant_cache: Dict[Tuple[RoomID, int], "GPTAssistant"] = {}

    def __init__(
        self, gpt_assistant_node_data: GPTAssistantModel, room: Room, default_variables: Dict
    ) -> None:
        Switch.__init__(
            self,
            switch_node_data=gpt_assistant_node_data,
            room=room,
            default_variables=default_variables,
        )
        self.log = self.log.getChild(gpt_assistant_node_data.get("id"))
        self.content: Dict = gpt_assistant_node_data
        self.client = openai.OpenAI(api_key=self.api_key)
        self.setup_assistant()
        self.middlewares: Optional[List[ASRMiddleware, TTMMiddleware]] = []

    @property
    def name(self) -> str:
        return self.render_data(data=self.content.get("name", ""))

    @property
    def instructions(self) -> str:
        return self.render_data(data=self.content.get("instructions", ""))

    @property
    def model(self) -> str:
        return self.render_data(data=self.content.get("model", ""))

    @property
    def assistant_id(self) -> str:
        return self.render_data(data=self.content.get("assistant_id", ""))

    @property
    def api_key(self) -> str:
        return self.render_data(data=self.content.get("api_key", ""))

    @property
    def initial_info(self) -> str:
        return self.render_data(self.content.get("initial_info", ""))

    @property
    def variable(self) -> str:
        return self.render_data(self.content.get("variable", ""))

    @property
    def inactivity_options(self) -> Dict[str, Any]:
        data: Dict = self.content.get("inactivity_options", {})
        self.chat_timeout: int = data.get("chat_timeout", 0)
        self.warning_message: str = self.render_data(data.get("warning_message", ""))
        self.time_between_attempts: int = data.get("time_between_attempts", 0)
        self.attempts: int = data.get("attempts", 0)
        return data

    @property
    def group_messages_timeout(self) -> int:
        return self.render_data(self.content.get("group_messages_timeout", 0))

    def setup_assistant(self):
        if self.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(self.assistant_id)
        else:
            self.assistant = self.client.beta.assistants.create(
                name=self.name,
                instructions=self.instructions,
                tools=[{"type": "code_interpreter"}],
                model=self.model,
            )

        self.thread = self.client.beta.threads.create()

    async def process_message(self, evt: Union[MessageEvent, str]) -> Union[str, List[Dict], None]:
        if isinstance(evt, str) or evt.content.msgtype == MessageType.TEXT:
            message = evt if isinstance(evt, str) else evt.content.body
            return {"type": "text", "text": message}
        elif evt.content.msgtype == MessageType.IMAGE:
            matrix_file = await self.room.matrix_client.download_media(evt.content.url)

            if evt.content.body and "forwarded" not in evt.content.body.lower():
                file_name = evt.content.body
            else:
                file_name = f"image.{mimetypes.guess_extension(mimetype(matrix_file))}"

            file = self.client.files.create(
                file=(file_name, matrix_file, mimetype(matrix_file)), purpose="vision"
            )
            return {"type": "image_file", "image_file": {"file_id": file.id}}
        elif evt.content.msgtype == MessageType.AUDIO:
            if not self.middlewares:
                return

            middlewares_sorted = {
                Middlewares(middleware.type): middleware for middleware in self.middlewares
            }

            audio_name = evt.content.file or "audio.ogg"
            _, text = await middlewares_sorted[Middlewares.ASR].run(
                audio_url=evt.content.url, audio_name=audio_name
            )

            return {"type": "text", "text": text}
        return

    async def add_message(self, messages: List[Union[MessageEvent, str]]):
        message_content = [await self.process_message(event) for event in messages]
        if not message_content:
            return

        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=message_content,
        )

    async def run_assistant(self, instructions: Optional[str] = None) -> str:
        # Runs the assistant with the given thread and assistant IDs.
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id,
            instructions=instructions,
        )

        while run.status == "in_progress" or run.status == "queued":
            await sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=self.thread.id, run_id=run.id)

            if run.status == "completed":
                messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
                message_dict = json.loads(messages.model_dump_json())
                most_recent_message = message_dict["data"][0]
                return most_recent_message["content"][0]["text"]["value"]

    def json_in_text(self, text: str) -> Dict | None:
        json_pattern = re.compile(r"```json(.*?)```", re.DOTALL)
        match = json_pattern.search(text)
        if match:
            json_str = match.group(1).strip()
            json_str = html.unescape(json_str)
            return json_str

    async def run(self, messages: Optional[List[MessageEvent]] = None):
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """

        if self.room.route.state == RouteState.INPUT:
            if not messages:
                self.log.warning("A problem occurred getting message event.")
                return

            await self.add_message(messages)
            assistant_resp = await self.run_assistant()
            response = int(assistant_resp) if assistant_resp.isdigit() else assistant_resp
            if json_str := self.json_in_text(response):
                response = json.loads(json_str)

            await self.room.set_variable(self.variable, value=response)

            if self.inactivity_options:
                await Util.cancel_task(task_name=self.room.room_id)

            output = await Switch.run(self, update_state=False, generate_event=False)
            o_connection = output if output else self.id
            await self.room.update_menu(o_connection)
        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"Room {self.room.room_id} enters gpt_assistant node {self.id}")

            if not await self.room.get_variable(self.variable):
                if self.initial_info:
                    await self.add_message([self.initial_info])

                assistant_resp = await self.run_assistant()
                response = int(assistant_resp) if assistant_resp.isdigit() else assistant_resp
                if json_str := self.json_in_text(response):
                    response = json.loads(json_str)
                await self.room.set_variable(self.variable, value=response)

            message = await self.room.get_variable(self.variable)
            await self.room.matrix_client.send_text(room_id=self.room.room_id, text=message)
            await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)

            if self.inactivity_options:
                await self.inactivity_task()

    async def inactivity_task(self):
        """It spawns a task to harass the client to enter information to input option

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object

        """

        self.log.debug(f"Inactivity loop starts in room: {self.room.room_id}")
        create_task(self.timeout_active_chats(), name=self.room.room_id)

    async def timeout_active_chats(self):
        """It sends messages in time intervals to communicate customer
        that not entered information to input option.

        Parameters
        ----------
        client : MatrixClient
            The Matrix client object.

        """

        # wait the given time to start the task
        await sleep(self.chat_timeout)

        count = 0
        while True:
            self.log.debug(f"Inactivity loop: {datetime.now()} -> {self.room.room_id}")
            if self.attempts == count:
                self.log.debug(f"INACTIVITY TRIES COMPLETED -> {self.room.room_id}")
                o_connection = await self.get_case_by_id("timeout")
                await self.room.update_menu(node_id=o_connection, state=None)

                await self.room.matrix_client.algorithm(room=self.room)
                break

            if self.warning_message:
                await self.room.matrix_client.send_text(
                    room_id=self.room.room_id, text=self.warning_message
                )

            await sleep(self.time_between_attempts)
            count += 1
