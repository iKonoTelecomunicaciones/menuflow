from typing import Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig

from .config import Config
from .db.migrations import upgrade_table
from .db.models import DBManager, User, Variable
from .jinja_template import FILTERS
from .menu import Menu


class MenuFlow(Plugin):
    dbm: DBManager
    menu: Menu

    async def start(self):
        await super().start()
        self.on_external_config_update()
        self.dbm = DBManager(self.database)
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

        user = await self.dbm.get_user_by_user_id(user_id=evt.sender, create=True)

        await self.algorithm(user=user, evt=evt)

    async def algorithm(self, user: User, evt: MessageEvent):

        self.log.debug(user.__dict__)

        if user.context.startswith("#message"):
            self.log.debug(f"A message node [{user.context}] will be executed")

            message = self.menu.get_message_by_id(user.context)

            if message.variable:
                user.set_variable(Variable(id=message.variable, value=evt.content.body))
                await self.dbm.create_variable(
                    user_id=user.user_id, variable_id=message.variable, value=evt.content.body
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
                pipeline.run(user=user)
            else:
                self.log.warning(
                    f"The pipeline [{user.context}] was not executed because it was not found"
                )

            if user.context.startswith("#message"):
                self.log.debug(f"A message node [{user.context}] will be executed")

                message = self.menu.get_message_by_id(user.context)

                if message.variable:
                    user.set_variable(Variable(id=message.variable, value=evt.content.body))
                    await self.dbm.create_variable(
                        user_id=user.user_id, variable_id=message.variable, value=evt.content.body
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
