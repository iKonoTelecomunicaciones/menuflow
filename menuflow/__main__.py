import asyncio
import sys
from typing import Dict, List

from mautrix.util.async_db import Database, DatabaseException
from mautrix.util.program import Program

from .api import client
from .api import init as init_api
from .config import Config
from .db import init as init_db
from .db import upgrade_table
from .email_client import EmailClient
from .menu import MenuClient
from .server import MenuFlowServer


class MenuFlow(Program):
    config: Config
    server: MenuFlowServer
    db: Database

    config_class = Config

    module = "menuflow"
    name = "menuflow"
    version = "0.1.0"
    command = "python -m menuflow"

    description = "A manager of bots that have conversation flows."

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
        management_api = init_api(self.config, self.loop)
        self.server = MenuFlowServer(management_api, self.config, self.loop)

    async def start_email_connections(self):
        self.log.debug("Starting email clients...")
        email_servers: List[Dict[str, str]] = self.config["menuflow.email_servers"]
        for server in email_servers:

            if server.get("server_id", "").lower().startswith("sample"):
                continue

            email_client = EmailClient(
                server_id=server.get("server_id"),
                host=server.get("host"),
                port=server.get("port"),
                username=server.get("username"),
                password=server.get("password"),
                start_tls=server.get("use_tls", True),
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
        asyncio.create_task(self.start_email_connections())

    async def stop(self) -> None:
        self.add_shutdown_actions(*(menu.stop() for menu in MenuClient.cache.values()))
        await super().stop()
        self.log.debug("Stopping server")
        try:
            await asyncio.wait_for(self.server.stop(), 5)
        except asyncio.TimeoutError:
            self.log.warning("Stopping server timed out")
        await self.db.stop()


MenuFlow().run()
