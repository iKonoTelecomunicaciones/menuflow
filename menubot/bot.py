import json
from typing import Type

from dataclass_wizard import fromdict
from maubot import MessageEvent, Plugin
from maubot.handlers import command, event
from mautrix.types import EventType
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .menu import MenuFlow, Variable

user_context = "origin"


class MenuBot(Plugin):

    menu: MenuFlow

    async def start(self):
        await super().start()
        self.on_external_config_update()

        self.menu = MenuFlow.from_dict(self.config["menu"])

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:

        self.log.debug(f"incoming message : {evt}")
        # Ignore bot messages
        if evt.sender in [self.client.mxid, self.config["whatsapp_bridge.mxid"]]:
            return

        message_opt = self.menu.get_message_by_id(user_context)
        if message_opt:
            message_opt.i_variable = Variable("i_variable", evt.content.body)
            await evt.client.send_text(room_id=evt.room_id, text=message_opt.check)
