from logging import getLogger
from typing import Optional

from mautrix.types import MessageEvent
from mautrix.util.logging import TraceLogger

from .config import Config
from .nodes import NodeType
from .room import Room, RoomState
from .utils import Util


class Thing:

    log: TraceLogger = getLogger("menuflow.thing")

    config: Config
    util: Util

    def __init__(self, config: Config, util: Util = None) -> None:
        self.config = config
        self.util = util

    async def algorithm(self, room: Room, event: Optional[MessageEvent] = None) -> None:

        if not room.node:
            self.log.debug(f"Room {room.room_id} does not have a node")
            await room.update_menu(node="start")
            return

        self.log.debug(f"The [room: {room.room_id}] [node: {room.node.id}] [state: {room.state}]")

        if room.node.type == NodeType.CHECKTIME:
            await room.execute_current_node()
        if room.node.type == NodeType.SWITCH:
            await room.execute_current_node()
        if room.node.type == NodeType.MESSAGE:
            await room.execute_current_node()
        if room.node.type == NodeType.INPUT:
            await room.execute_current_node(input_event=event)
            if room.state == RoomState.INPUT:
                return

        if room.node.type == NodeType.HTTPREQUEST:

            middleware = room.menuflow.middleware(room=room, middleware_id=room.node.middleware)

            if middleware:
                middleware.config = self.config

            self.log.debug(f"Room {room.room_id} enters http_request node {room.node.id}")
            try:
                status, response = await room.node.run(
                    session=self.api.session, middleware=middleware
                )
                self.log.info(f"http_request node {room.node.id} had a status of {status}")

                if status == 401:
                    self.HTTP_ATTEMPTS.update(
                        {
                            room.room_id: {
                                "last_http_node": room.node.id,
                                "attempts_count": self.HTTP_ATTEMPTS.get(room.room_id).get(
                                    "attempts_count"
                                )
                                + 1
                                if self.HTTP_ATTEMPTS.get(room.room_id)
                                else 1,
                            }
                        }
                    )
                    self.log.debug(
                        "HTTP auth attempt"
                        f"{self.HTTP_ATTEMPTS[room.room_id]['attempts_count']}, trying again ..."
                    )

                if not status in [200, 201]:
                    self.log.error(response)
                else:
                    self.HTTP_ATTEMPTS.update(
                        {room.room_id: {"last_http_node": None, "attempts_count": 0}}
                    )
            except Exception as e:
                self.log.exception(e)
                return

            if (
                self.HTTP_ATTEMPTS.get(room.room_id)
                and self.HTTP_ATTEMPTS[room.room_id]["last_http_node"] == room.node.id
                and self.HTTP_ATTEMPTS[room.room_id]["attempts_count"] >= middleware._attempts
            ):
                self.log.debug("Attempts limit reached, o_connection set as `default`")
                self.HTTP_ATTEMPTS.update(
                    {room.room_id: {"last_http_node": None, "attempts_count": 0}}
                )
                await room.update_menu(await room.node.get_case_by_id("default"), None)

        if room.state == RoomState.END:
            self.log.debug(f"The room {room.room_id} has terminated the flow")
            await room.update_menu(node=RoomState.START)
            return

        await self.algorithm(room=room, event=event)
