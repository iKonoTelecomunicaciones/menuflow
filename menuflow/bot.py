from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .db import User, Variable, upgrade_table
from .jinja.jinja_template import FILTERS
from .menu import Menu


class MenuFlow(Plugin):
    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()

        for table in [User, Variable]:
            table.db = self.database

        self.menu = Menu.deserialize(self.config["menu"])

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

        user = await User.get_by_user_id(user_id=evt.sender, create=True)

        await self.algorithm(user=user, evt=evt)

    async def algorithm(self, user: User, evt: MessageEvent):
        """If the user's context is a message node, execute the message node,
        if the message node has a variable, set the variable,
        if the message node has a wait, return,
        if the message node has a message node as a context, execute the message node,
        if the user's context is a pipeline node, execute the pipeline node,
        if the pipeline node has a message node as a context, execute the message node.

        Parameters
        ----------
        user : User
            User
        evt : MessageEvent
            MessageEvent

        Returns
        -------
            The return value is the value of the last expression in the function body,
            or None if the function executes a return statement with no arguments
            or if the function ends without executing a return statement.

        """

        self.log.debug(user.__dict__)

        if user.context.startswith("#message"):
            self.log.debug(f"A message node [{user.context}] will be executed")

            message = self.menu.get_message_by_id(user.context)

            if message.variable:
                user.set_variable(Variable(id=message.variable, value=evt.content.body))
                await Variable.insert(
                    fk_user=user.id, variable_id=message.variable, value=evt.content.body
                )

            if message:
                await message.run(
                    user=user, room_id=evt.room_id, client=evt.client, i_variable=evt.content.body
                )
            else:
                self.log.warning(
                    f"The message [{user.context}] was not executed because it was not found"
                )

            if user.context == message.id:
                self.log.warning("Crazy that's a loop")
                return

            if message.wait:
                return

            if user.context.startswith("#message"):
                await self.algorithm(user, evt)

        if user.context.startswith("#pipeline"):

            self.log.debug(f"A pipeline node [{user.context}] will be executed")

            pipeline = self.menu.get_pipeline_by_id(user.context)

            if pipeline:
                await pipeline.run(user=user)
            else:
                self.log.warning(
                    f"The pipeline [{user.context}] was not executed because it was not found"
                )

            if user.context.startswith("#message"):
                self.log.debug(f"A message node [{user.context}] will be executed")

                message = self.menu.get_message_by_id(user.context)

                if message.variable:
                    user.set_variable(Variable(id=message.variable, value=evt.content.body))
                    await Variable.insert(
                        fk_user=user.id, variable_id=message.variable, value=evt.content.body
                    )

                if message:
                    await message.run(
                        user=user,
                        room_id=evt.room_id,
                        client=evt.client,
                        i_variable=evt.content.body,
                    )
                else:
                    self.log.warning(
                        f"The message [{user.context}] was not executed because it was not found"
                    )
