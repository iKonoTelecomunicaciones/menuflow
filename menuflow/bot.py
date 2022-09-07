from __future__ import annotations

from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig
from menuflow.message import Message
from menuflow.pipeline import Pipeline

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
        if evt.sender in self.config["ignore"] or evt.sender == evt.client.mxid:
            return

        try:
            user = await User.get_by_user_id(user_id=evt.sender)
        except Exception as e:
            self.log.exception(e)
            return

        if not user:
            return

        await self.algorithm(user=user, evt=evt)

    async def algorithm(self, user: User, evt: MessageEvent):
        """If the user is in the state of inputting a variable,
        then set the variable and update the menu.
        If the user is in the state of executing a message,
        then show the message and update the menu.
        If the user is in the state of executing a pipeline, then run the pipeline

        Parameters
        ----------
        user : User
            User - The user object that is currently interacting with the bot.
        evt : MessageEvent
            MessageEvent

        Returns
        -------
            A list of dictionaries

        """

        state: Pipeline | Message = await self.search_user_state(user=user)

        if user.state == "INPUT_VARIABLE":
            await user.set_variable(state.variable, evt.content.body)
            await user.update_menu(context=state.o_connection)
            state: Pipeline | Message = await self.search_user_state(user=user)

        if isinstance(state, Message):

            if state.o_connection is None:
                return

            self.log.debug(f"A message state [{state.id}] will be executed")

            await state.show_message(user=user, room_id=evt.room_id, client=evt.client)

            if state.variable:
                await user.update_menu(context=state.id, state="INPUT_VARIABLE")
                return
            else:
                await user.update_menu(context=state.o_connection)

        if isinstance(state, Pipeline):
            await state.run(user=user)

        await self.algorithm(user=user, evt=evt)

    async def search_user_state(self, user: User) -> Message | Pipeline | None:
        """It returns the message or pipeline that the user is currently in.

        Parameters
        ----------
        user : User
            The user object that is currently being processed.

        Returns
        -------
            A message or pipeline.

        """

        if user.context.startswith("m"):
            return self.menu.get_message_by_id(user.context)

        if user.context.startswith("p"):
            return self.menu.get_pipeline_by_id(user.context)
