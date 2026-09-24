from __future__ import annotations

import asyncio
from logging import getLogger
from typing import TYPE_CHECKING, Dict

from mautrix.types import RoomID
from mautrix.util.logging import TraceLogger

from .config import Config

if TYPE_CHECKING:
    from .matrix import MatrixHandler


class RoomMonitor:
    MONITORING_ROOMS: Dict[RoomID, RoomMonitor] = {}
    log: TraceLogger = getLogger("menuflow.room_monitor")
    client: MatrixHandler

    default_time_to_ignore = None
    ignored_counter_threshold = None
    message_threshold = None
    time_multiplier = None
    tag_data = None
    init_checker_limit_timer = None

    def __init__(
        self,
        room_id: RoomID | None = None,
    ) -> None:
        self.client = self.client
        if room_id is None:
            return

        self.room_id = room_id
        self.message_counter = 0
        self.ignore = False
        self.ignored_counter = 0
        self.time_to_ignore = self.default_time_to_ignore
        self.running_limit_task = False
        self.running_restore_task = False
        self.task_name = f"{room_id}_message_traceback"

    @classmethod
    def init_cls(cls, client: MatrixHandler, config: Config) -> None:
        cls.client = client
        cls.default_time_to_ignore = config["menuflow.bot_war.time_to_ignore"]
        cls.ignored_counter_threshold = config["menuflow.bot_war.ignored_counter_threshold"]
        cls.message_threshold = config["menuflow.bot_war.message_threshold"]
        cls.time_multiplier = config["menuflow.bot_war.time_multiplier"]
        cls.tag_data = config["menuflow.bot_war.tag_data"]
        cls.init_checker_limit_timer = config["menuflow.bot_war.init_checker_limit_timer"]

    def _get_or_create(self, room_id: RoomID) -> RoomMonitor:
        if room_id not in self.MONITORING_ROOMS:
            self.log.debug(f"[{room_id}] Adding room to message traceback")
            self.MONITORING_ROOMS[room_id] = RoomMonitor(room_id=room_id)
        return self.MONITORING_ROOMS[room_id]

    async def start_monitoring(self, room_id: RoomID) -> bool:
        """
        Run bot-war checks and timers for an incoming message

        Returns True if the message must not be processed further
        """
        monitor = self._get_or_create(room_id)

        running_limit_task = monitor.running_limit_task
        running_restore_task = monitor.running_restore_task
        time_to_ignore = monitor.time_to_ignore
        checker_limit_timer = monitor.init_checker_limit_timer

        loop: asyncio.AbstractEventLoop | None = None
        if monitor.ignore is False:
            if running_limit_task is False:
                monitor.running_limit_task = True
                loop = asyncio.get_event_loop()
                loop.call_later(checker_limit_timer, monitor.conversation_status)
            return False

        if running_restore_task is False:
            monitor.log.warning(
                f"[{monitor.room_id}] Ignoring messages for {time_to_ignore} seconds..."
            )
            monitor.running_restore_task = True
            loop = asyncio.get_event_loop()
            loop.call_later(time_to_ignore, monitor.conversation_status, True)
        return True

    def conversation_status(self, ignore: bool = False):
        if not ignore:
            asyncio.create_task(self.check_message_limit(), name=self.task_name)
        else:
            asyncio.create_task(self.restore_state(), name=self.task_name)

    def register_message(self, room_id: RoomID) -> None:
        self._get_or_create(room_id).message_counter += 1

    async def check_message_limit(self) -> None:
        self.log.debug(f"[{self.room_id}] Checking message limit...")
        if self.message_counter >= self.message_threshold:
            self.log.warning(
                f"[{self.room_id}] Message limit reached, the messages will be ignored"
            )
            self.ignore = True
            self.ignored_counter += 1
        else:
            self.running_limit_task = False
            self.message_counter = 0

    async def restore_state(self) -> None:
        self.ignore = False
        self.message_counter = 0
        self.running_limit_task = False
        self.running_restore_task = False

        self.log.warning(f"[{self.room_id}] Restoring state to unignore messages")
        if self.ignored_counter >= self.ignored_counter_threshold:
            self.ignored_counter = 0
            self.time_to_ignore = self.default_time_to_ignore
            await self.set_room_tag_bot()
        else:
            self.time_to_ignore *= self.time_multiplier

    async def set_room_tag_bot(self) -> None:
        room_tag = self.tag_data
        try:
            self.log.debug(f"[{self.room_id}] Setting room tag {room_tag.get('text')}...")
            url_path = f"/_matrix/client/v3/rooms/{self.room_id}/state/ik.chat.tag"
            request_response = await self.client.api.session.put(
                url=f"{self.client.api.base_url}{url_path}",
                headers={"Authorization": f"Bearer {self.client.api.token}"},
                json={"tags": [self.tag_data]},
            )
            request_response_json = await request_response.json()
            if request_response_json.get("error"):
                self.log.error(
                    f"[{self.room_id}] Error setting room tag {room_tag.get('text')}: "
                    f"{request_response_json.get('error')}"
                )

            self.log.debug(f"[{self.room_id}] Setting portal to space for {room_tag.get('id')}...")
            url_path = (
                f"/_matrix/client/v3/rooms/{room_tag.get('id')}/state/m.space.child/{self.room_id}"
            )
            request_response = await self.client.api.session.put(
                url=f"{self.client.api.base_url}{url_path}",
                headers={"Authorization": f"Bearer {self.client.api.token}"},
                json={"via": [self.client.domain], "suggested": False},
            )
            request_response_json = await request_response.json()
            if request_response_json.get("error"):
                self.log.error(
                    f"[{self.room_id}] Error setting portal to space {room_tag.get('id')}: "
                    f"{request_response_json.get('error')}"
                )

        except Exception as error:
            self.log.error(
                f"[{self.room_id}] Error adding portal to tag {room_tag.get('text')} "
                f"or space {room_tag.get('id')}: {error}"
            )

    @classmethod
    async def is_a_bot(cls, room_id: RoomID) -> bool:
        conversation_tags = None
        try:
            conversation_tags = await cls.client.api.session.get(
                url=f"{cls.client.api.base_url}/_matrix/client/v3/rooms/{room_id}/state/ik.chat.tag",
                headers={"Authorization": f"Bearer {cls.client.api.token}"},
            )
        except Exception as error:
            cls.log.error(f"Error checking if the {room_id} is a bot: {error}")

        if conversation_tags:
            tags_payload = await conversation_tags.json()
            bot_tag_text = cls.tag_data["text"]
            tag_list = tags_payload.get("tags", tags_payload) if tags_payload else []
            if tag_list and any(
                (tag.get("text") if isinstance(tag, dict) else tag) == bot_tag_text
                for tag in tag_list
            ):
                return True

        return False
