import json
from typing import Type

from dataclass_wizard import fromdict
from maubot import MessageEvent, Plugin
from maubot.handlers import command, event
from mautrix.types import EventType
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .menu import Menu


class MenuBot(Plugin):

    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()

        menu = Menu.from_dict(self.config["menu"])
        menu.log = self.log
        menu.build_menu_message()
        self.menu = menu

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:

        # Ignore bot messages
        if evt.sender in [self.client.mxid, self.config["whatsapp_bridge.mxid"]]:
            return

        await self.client.send_text(room_id=evt.room_id, text=self.menu.menu_message)
