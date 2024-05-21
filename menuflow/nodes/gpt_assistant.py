import json
from asyncio import sleep
from typing import Dict, Optional

import openai

from ..db.route import RouteState
from ..repository import GPTAssistant as GPTAssistantModel
from ..room import Room
from .base import Base


class GPTAssistant(Base):
    assistant_cache: Dict[int, "GPTAssistant"] = {}

    def __init__(
        self, gpt_assistant_node_data: GPTAssistantModel, room: Room, default_variables: Dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(gpt_assistant_node_data.get("id"))
        self.content: Dict = gpt_assistant_node_data
        self.client = openai.OpenAI(api_key=self.api_key)
        self.setup_assistant()

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
    def user_input(self) -> str:
        return self.render_data(data=self.content.get("user_input", ""))

    @property
    def variable(self) -> str:
        return self.render_data(data=self.content.get("variable", ""))

    @property
    def o_connection(self) -> str:
        return self.render_data(data=self.content.get("o_connection", ""))

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

    def add_message(self, content: str):
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=content,
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

    async def _update_node(self, o_connection: str):
        await self.room.update_menu(
            node_id=o_connection,
            state=RouteState.END if not o_connection else None,
        )

    async def run(self):
        self.add_message(str(self.user_input))
        assistant_resp = await self.run_assistant()
        await self.room.set_variable(
            self.variable,
            int(assistant_resp) if assistant_resp.isdigit() else assistant_resp,
        )
        await self._update_node(self.o_connection)
