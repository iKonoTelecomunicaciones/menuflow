from __future__ import annotations

from logging import getLogger

from mautrix.types import RoomID, UserID

from menuflow.config import Config
from menuflow.db.client import Client as DBClient
from menuflow.db.flow import Flow as DBFlow
from menuflow.db.module import Module as DBModule
from menuflow.db.tag import Tag as DBTag

log = getLogger("menuflow.flow_sync")


class FlowSync:
    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    async def build_active_tag_content(tag_id: int) -> dict:
        """Build the content of the active tag.

        Args:
            tag_id (int): The id of the tag to build the content for.

        Returns:
            dict: The content of the active tag.
        """
        tag_obj = await DBTag.get_by_id(tag_id)
        modules = await DBModule.get_tag_modules(tag_obj.id)

        return {
            "flow_variables": tag_obj.flow_vars,
            "nodes": [node for module in modules for node in module.get("nodes", [])],
            "loaded_metadata": {
                "tag_info": {"name": tag_obj.name, "id": tag_obj.id},
                "loaded_modules_ids": [module.id for module in modules],
            },
        }

    async def update_flow_db_clients(
        self, flow_id: int, content: dict, uuid: str | None = None
    ) -> None:
        """Update the flow of the db clients.

        Args:
            flow_id (int): The id of the flow to update.
            content (dict): The content of the flow to update.
            uuid (str | None): The uuid of the operation.
        """
        from menuflow.menu import MenuClient

        db_clients = await DBClient.get_by_flow_id(flow_id)
        log.info(f"({uuid}) -> Updating cache for {len(db_clients)} clients")

        for db_client in db_clients:
            client = MenuClient.cache[db_client.id]
            await client.flow_cls.load_flow(flow_mxid=client.id, content=content)

    async def check_active_tag(self, room_id: RoomID, mxid: UserID, loaded_metadata: dict) -> None:
        """Check if the active tag is the same as the loaded tag.

        Args:
            room_id (RoomID): The id of the room to check.
            mxid (str): The mxid of the flow to check.
            flow (RuntimeFlow): The flow to check.
        """
        flow_db = await DBFlow.get_by_mxid(mxid)
        active_tag = await DBTag.get_active_tag(flow_db.id)
        loaded_tag_id = loaded_metadata.get("tag_info", {}).get("id")

        if active_tag.id == loaded_tag_id:
            return

        log.critical(
            f"[{room_id}] Danger! The active tag is not the same as the loaded tag. "
            f"Cached data: {loaded_metadata}. Active tag db: {active_tag.id}"
        )

        content = await self.build_active_tag_content(active_tag.id)
        await self.update_flow_db_clients(flow_db.id, content)
