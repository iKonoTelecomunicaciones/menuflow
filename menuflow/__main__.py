import asyncio
import sys
from typing import Dict
import yaml

from mautrix.util.async_db import Database, DatabaseException
from mautrix.util.program import Program

from .repository.middlewares import EmailServer
from .repository.flow_utils import FlowUtils as FlowUtilsModel

from .api import client
from .api import init as init_api
from .config import Config
from .db import init as init_db
from .db import upgrade_table
from .email_client import EmailClient
from .menu import MenuClient
from .server import MenuFlowServer
from .flow_utils import FlowUtils


class MenuFlow(Program):
    config: Config
    server: MenuFlowServer
    db: Database
    flow_utils: FlowUtils | None = None

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
        self.load_flow_utils()

    def load_flow_utils(self):
        try:
            path = f"/data/flow_utils.yaml"
            with open(path, "r") as file:
                flow: Dict = yaml.safe_load(file)
            flow_utils_model = FlowUtilsModel(**flow)
            self.flow_utils = FlowUtils(flow_utils_model)
        except FileNotFoundError:
            self.log.warning("File flow_utils.yaml not found")

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
        if self.flow_utils:
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
