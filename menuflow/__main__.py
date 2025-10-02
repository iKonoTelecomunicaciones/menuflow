import asyncio
import sys
from typing import Dict

from mautrix.util.async_db import Database, DatabaseException
from mautrix.util.program import Program

from menuflow.webhook.webhook_queue import WebhookQueue

from .config import Config
from .db import init as init_db
from .db import upgrade_table
from .email_client import EmailClient
from .events import NatsPublisher
from .flow import Flow
from .flow_utils import FlowUtils
from .menu import MenuClient
from .repository.middlewares import EmailServer
from .server import MenuFlowServer
from .version import version
from .web.management_api import ManagementAPI


class MenuFlow(Program):
    config: Config
    server: MenuFlowServer
    db: Database
    flow_utils: FlowUtils | None = None

    config_class = Config

    module = "menuflow"
    name = "menuflow"
    version = version
    command = "python -m menuflow"

    description = "A manager of bots that have conversation flows."

    management_api: ManagementAPI

    def prepare_arg_parser(self) -> None:
        super().prepare_arg_parser()

    def prepare_db(self) -> None:
        self.db = Database.create(
            self.config["menuflow.database"],
            upgrade_table=upgrade_table,
            db_args=self.config["menuflow.database_opts"],
            owner_name=self.name,
        )
        init_db(self.db)

    def prepare(self) -> None:
        super().prepare()
        self.prepare_db()
        MenuClient.init_cls(self)
        NatsPublisher.init_cls(self.config)
        self.flow_utils = FlowUtils()
        self.management_api = ManagementAPI(
            config=self.config,
            loop=self.loop,
            flow_utils=self.flow_utils,
        )
        self.server = MenuFlowServer(self.management_api.app, self.config, self.loop)
        Flow.init_cls(self.flow_utils)

    async def start_email_connections(self):
        self.log.debug("Starting email clients...")
        email_servers: Dict[str, EmailServer] = self.flow_utils.get_email_servers()
        for key, server in email_servers.items():
            if server.server_id.lower().startswith("sample"):
                continue

            email_client = EmailClient(
                server_id=server.server_id,
                host=server.host,
                port=server.port,
                username=server.username,
                password=server.password,
                start_tls=server.start_tls,
            )
            await email_client.login()
            email_client._add_to_cache()

    async def start_db(self) -> None:
        self.log.debug("Starting database...")

        try:
            await self.db.start()
            # await self.state_store.upgrade_table.upgrade(self.db)
        except DatabaseException as e:
            self.log.critical("Failed to initialize database", exc_info=e)
            if e.explanation:
                self.log.info(e.explanation)
            sys.exit(25)

    async def system_exit(self) -> None:
        if hasattr(self, "db"):
            self.log.trace("Stopping database due to SystemExit")
            await self.db.stop()

    async def start(self) -> None:
        await self.start_db()
        await asyncio.gather(*[menu.start() async for menu in MenuClient.all()])
        await super().start()
        await self.server.start()
        await NatsPublisher.get_connection()
        await WebhookQueue(config=self.config).save_events_to_queue()
        if self.flow_utils:
            asyncio.create_task(self.start_email_connections())

    async def stop(self) -> None:
        await NatsPublisher.close_connection()
        self.add_shutdown_actions(*(menu.stop() for menu in MenuClient.cache.values()))
        await super().stop()
        self.log.debug("Stopping server")
        try:
            await asyncio.wait_for(self.server.stop(), 5)
        except asyncio.TimeoutError:
            self.log.warning("Stopping server timed out")
        await self.db.stop()


MenuFlow().run()
