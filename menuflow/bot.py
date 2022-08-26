import json
from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.config import BaseProxyConfig

import jinja_template #

from .config import Config
from .menu import Menu
from .user import User


class MenuFlow(Plugin):

    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()

        self.menu = Menu.from_dict(self.config["menu"])

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:

        self.log.debug(f"Incoming message : {evt}")
        # Ignore bot messages
        if evt.sender in self.config["ignore"] or evt.sender == evt.client.mxid:
            return

        user: User = None

        if user.context.startswith("#message"):
            message = self.menu.get_message_by_id(user.context)

            if message:
                await message.run(
                    user=user, room_id=evt.room_id, client=evt.client, i_variable=evt.content.body
                )

        if user.context.startswith("#pipeline"):
            pipeline = self.menu.get_pipeline_by_id(user.context)

            if pipeline:
                await pipeline.run(
                    user=user, room_id=evt.room_id, client=evt.client, i_variable=evt.content.body
                )
