import json
from typing import Type

from dataclass_wizard import fromdict
from maubot import MessageEvent, Plugin
from maubot.handlers import command, event
from mautrix.types import EventType
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .menu import Menu, Variable
from .primitive import IConnection, OConnection

USER_CONTEXT: IConnection = "#origin"
USER_STATE = "SHOW_MSG"


class MenuFlow(Plugin):

    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()

        self.menu = Menu.from_dict(self.config["menu"])
        self.menu.log = self.log
        self.log.debug(repr(self.menu))

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:

        self.log.debug(f"Incoming message : {evt}")
        # Ignore bot messages
        if evt.sender in self.config["ignore_list"] or evt.sender == evt.client.mxid:
            return

        self.log.debug(f"###1 {USER_CONTEXT}")
        self.log.debug(f"###1 {USER_STATE}")

        msg = await self.menu_algorithm(
            user_context=USER_CONTEXT, user_state=USER_STATE, evt_msg=evt
        )

        self.log.debug(f"###2 {USER_CONTEXT}")
        self.log.debug(f"###2 {USER_STATE}")

        # message_opt = self.menu.get_message_by_id(user_context)
        # if message_opt:
        #     message_opt.i_variable = Variable("i_variable", evt.content.body)
        #     await evt.client.send_text(room_id=evt.room_id, text=message_opt.check)

    async def menu_algorithm(
        self, user_context: str, user_state: str, evt_msg: MessageEvent
    ) -> None:
        global USER_CONTEXT
        global USER_STATE

        message_opt = self.menu.get_message_by_id(user_context)


        if USER_STATE == "SHOW_MSG":
            if message_opt:
                await evt_msg.client.send_text(room_id=evt_msg.room_id, text=message_opt.text)

                if message_opt.i_rule:
                    USER_STATE = "CHECK_RULE"

            return

        if USER_STATE == "CHECK_RULE":
            message_opt.i_variable = Variable("i_variable", evt_msg.content.body)
            _result, msg = message_opt.check
            if _result and msg.startswith("#message"):
                USER_CONTEXT = msg
                USER_STATE = "SHOW_MSG"

            elif _result and msg.startswith("#filter"):
                USER_CONTEXT = msg
                USER_STATE = "CHECK_FILTERS"


            elif not _result:
                await evt_msg.client.send_text(room_id=evt_msg.room_id, text=msg)


        if USER_STATE == "CHECK_FILTERS":
            _filter = self.menu.get_filter_by_id(USER_CONTEXT)
            connection: OConnection = self.menu.check_filter(_filter)
            USER_CONTEXT = connection
            if connection.startswith("#message"):
                USER_STATE = "SHOW_MSG"
                await self.menu_algorithm(USER_CONTEXT, USER_STATE, evt_msg)


            elif connection.startswith("#filter"):
                USER_STATE = "CHECK_FILTERS"
                await self.menu_algorithm(USER_CONTEXT, USER_STATE, evt_msg)

