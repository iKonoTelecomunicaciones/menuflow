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

    def __init__(
        self,
        client: MatrixHandler,
        config: Config,
        room_id: RoomID | None = None,
    ) -> None:
        self.client = client
        self.config = config
        if room_id is None:
            return

        self.room_id = room_id
        self.message_counter = 0
        self.ignore = False
        self.ignored_counter = 0
        self.time_to_ignore = config["menuflow.bot_war.time_to_ignore"]
        self.running_limit_task = False
        self.running_restore_task = False
        self.task_name = f"{room_id}_message_traceback"

    def _get_or_create(self, room_id: RoomID) -> RoomMonitor:
        if room_id not in self.MONITORING_ROOMS:
            self.log.debug(f"Adding room {room_id} to message traceback")
            self.MONITORING_ROOMS[room_id] = RoomMonitor(
                client=self.client,
                config=self.config,
                room_id=room_id,
            )
        return self.MONITORING_ROOMS[room_id]

    async def start_monitoring(self, room_id: RoomID) -> bool:
        """
        Run bot-war checks and timers for an incoming message

        Returns True if the message must not be processed further
        """
        monitor = self._get_or_create(room_id)

        if await monitor.is_a_bot():
            monitor.log.debug(f"The room {monitor.room_id} is a bot, ignoring messages...")
            return True

        running_limit_task = monitor.running_limit_task
        running_restore_task = monitor.running_restore_task
        time_to_ignore = monitor.time_to_ignore
        checker_limit_timer = monitor.config["menuflow.bot_war.init_checker_limit_timer"]

        loop: asyncio.AbstractEventLoop | None = None
        if running_limit_task is False or running_restore_task is False:
            loop = asyncio.get_event_loop()

        if monitor.ignore is False:
            if running_limit_task is False:
                monitor.running_limit_task = True
                loop.call_later(checker_limit_timer, monitor.conversation_status)
            return False

        if running_restore_task is False:
            monitor.log.warning(
                f"Ignoring messages of room {monitor.room_id} for {time_to_ignore} seconds..."
            )
            monitor.running_restore_task = True
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
        self.log.debug(f"Checking message limit for room {self.room_id}...")
        if self.message_counter >= self.config["menuflow.bot_war.message_threshold"]:
            self.log.warning(
                f"Message limit reached for room {self.room_id}, the messages will be ignored"
            )
            self.ignore = True
            self.ignored_counter += 1
        else:
            self.running_limit_task = False

    async def restore_state(self) -> None:
        self.ignore = False
        self.message_counter = 0
        self.running_limit_task = False
        self.running_restore_task = False

        self.log.warning(f"Restoring state for room {self.room_id} to unignore messages")
        if self.ignored_counter == self.config["menuflow.bot_war.ignored_counter_threshold"]:
            self.ignored_counter = 0
            self.time_to_ignore = self.config["menuflow.bot_war.time_to_ignore"]
            await self.set_room_tag_bot()
        else:
            self.time_to_ignore *= self.config["menuflow.bot_war.time_multiplier"]

    async def set_room_tag_bot(self) -> None:
        room_tag = self.config["menuflow.bot_war.tag_data"]
        try:
            self.log.debug(f"Setting room tag {room_tag.get('text')} for {self.room_id}...")
            url_path = f"/_matrix/client/v3/rooms/{self.room_id}/state/ik.chat.tag/"
            request_response = await self.client.api.session.put(
                url=f"{self.client.api.base_url}{url_path}",
                headers={"Authorization": f"Bearer {self.client.api.token}"},
                json={"tags": [self.config["menuflow.bot_war.tag_data"]]},
            )
            request_response_json = await request_response.json()
            if request_response_json.get("error"):
                self.log.error(
                    f"Error setting room tag {room_tag.get('text')} for {self.room_id}: "
                    f"{request_response_json.get('error')}"
                )

            self.log.debug(f"Setting portal {self.room_id} to space for {room_tag.get('id')}...")
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
                    f"Error setting portal {self.room_id} to space for {room_tag.get('id')}: "
                    f"{request_response_json.get('error')}"
                )

        except Exception as error:
            self.log.error(
                f"Error adding portal {self.room_id} "
                f"to {room_tag.get('text')} tag "
                f"or space {room_tag.get('id')}: {error}"
            )

    async def is_a_bot(self) -> bool:
        conversation_tags = None
        try:
            conversation_tags = await self.client.api.session.get(
                url=f"{self.client.api.base_url}/_matrix/client/v3/rooms/{self.room_id}/state",
                headers={"Authorization": f"Bearer {self.client.api.token}"},
            )
        except Exception as error:
            self.log.error(f"Error checking if the {self.room_id} is a bot: {error}")

        if conversation_tags:
            bot_tag_text = self.config["menuflow.bot_war.tag_data"]["text"]
            for room_event in await conversation_tags.json():
                if room_event.get("type") != "ik.chat.tag":
                    continue
                tags = (room_event.get("content") or {}).get("tags")
                if tags and any(tag.get("text") == bot_tag_text for tag in tags):
                    return True

        return False
