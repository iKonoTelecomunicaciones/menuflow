from __future__ import annotations

from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig
from menuflow.node import Input, Message

from .config import Config
from .db.migrations import upgrade_table
from .db.user import User as DBUser
from .db.variable import Variable as DBVariable
from .jinja.jinja_template import FILTERS
from .menu import Menu
from .user import User


class MenuFlow(Plugin):
    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()
        await self.initialize_tables()
        self.menu = Menu.deserialize(self.config["menu"])

    async def initialize_tables(self):
        for table in [DBUser, DBVariable]:
            table.db = self.database

    @classmethod
    def get_db_upgrade_table(cls) -> UpgradeTable:
        return upgrade_table

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @event.on(EventType.ROOM_MESSAGE)
    async def event_handler(self, evt: MessageEvent) -> None:

        # Ignore bot messages
        if evt.sender in self.config["users_ignore"] or evt.sender == evt.client.mxid:
            return

        try:
            user = await User.get_by_user_id(user_id=evt.sender)
            user.menu = self.menu
        except Exception as e:
            self.log.exception(e)
            return

        if not user:
            return

        await self.algorithm(user=user, evt=evt)

    async def algorithm(self, user: User, evt: MessageEvent) -> None:
        """> If the current node is an input node, then show the message and wait for the user to input a value. If the current node is a message node, then show the message and move to the next node

        Parameters
        ----------
        user : User
            User - The user object that is currently interacting with the bot.
        evt : MessageEvent
            Incoming MessageEvent
        """

        if user.state == "input":
            await user.set_variable(user.node.variable, evt.content.body)

            if user.node.o_connection:
                await user.update_menu(context=user.node.o_connection)
            else:
                o_connection = await user.node.run(variables=user.variables_data)
                await user.update_menu(context=o_connection)

        if isinstance(user.node, Input) and user.state != "input":
            await user.node.show_message(
                variables=user.variables_data, room_id=evt.room_id, client=evt.client
            )
            self.log.debug(f"Input {user.node}")
            await user.update_menu(context=user.node.id, state="input")
            return

        if isinstance(user.node, Message):
            await user.node.show_message(
                variables=user.variables_data, room_id=evt.room_id, client=evt.client
            )
            self.log.debug(f"Message {user.node}")

            if user.node.o_connection is None:
                return

            await user.update_menu(context=user.node.o_connection)
            await self.algorithm(user=user, evt=evt)
