from __future__ import annotations

from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .db.migrations import upgrade_table
from .db.user import User as DBUser
from .jinja.jinja_template import FILTERS
from .menu import Menu
from .nodes import HTTPRequest, Input, Message
from .user import User


class MenuFlow(Plugin):
    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()
        await self.initialize_tables()
        self.menu = Menu.deserialize(self.config["menu"])

    async def initialize_tables(self):
        for table in [DBUser]:
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
        """If the user is in the input state, then set the variable to the user's input,
        and if the node has an output connection, then update the menu to the output connection.
        Otherwise, run the node and update the menu to the output connection.
        If the node is an input node and the user is not in the input state,
        then show the message and update the menu to the node's id and set the state to input.
        If the node is a message node, then show the message and if the node has an output connection,
        then update the menu to the output connection and run the algorithm again

        Parameters
        ----------
        user : User
            User - the user object
        evt : MessageEvent
            The event that triggered the algorithm.

        Returns
        -------
            The return value is the result of the last expression in the function body.

        """

        # This is the case where the user is in the input state.
        # In this case, the variable is set to the user's input, and if the node has an output connection,
        # then the menu is updated to the output connection.
        # Otherwise, the node is run and the menu is updated to the output connection.
        if user.state == "input":
            await user.set_variable(user.node.variable, evt.content.body)

            if user.node.o_connection:
                await user.update_menu(context=user.node.o_connection)
            else:
                o_connection = await user.node.run(user=user)
                await user.update_menu(context=o_connection)

        # This is the case where the user is not in the input state and the node is an input node.
        # In this case, the message is shown and the menu is updated to the node's id and the state is set to input.
        if user.node.type == "input" and user.state != "input":
            await user.node.show_message(
                variables=user._variables, room_id=evt.room_id, client=evt.client
            )
            self.log.debug(f"Input {user.node}")
            await user.update_menu(context=user.node.id, state="input")
            return

        # Showing the message and updating the menu to the output connection.
        if user.node.type == "message":
            await user.node.show_message(
                variables=user._variables, room_id=evt.room_id, client=evt.client
            )
            self.log.debug(f"Message {user.node}")

            if user.node.o_connection is None:
                return

            await user.update_menu(context=user.node.o_connection)

        if user.node.type == "http_request":
            self.log.debug(f"HTTPRequest {user.node}")

            await user.node.request(user=user, session=evt.client.api.session)

        await self.algorithm(user=user, evt=evt)
