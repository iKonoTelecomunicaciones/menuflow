from __future__ import annotations

import asyncio
from logging import getLogger
from mautrix.types import EventType, RoomID, StateEvent
from mautrix.util.logging import TraceLogger
from .db.room import Room as DBRoom
from menuflow.utils.types import ProtectedVars

from .config import Config


class RoomMonitor:
    TAG_STATE_EVENT_TYPE = EventType.find("ik.chat.tag", EventType.Class.STATE)
    MONITORING_ROOMS: dict[RoomID, RoomMonitor] = {}
    log: TraceLogger = getLogger("menuflow.room_monitor")
    api = None
    domain = None

    default_time_to_ignore = None
    ignored_counter_threshold = None
    message_threshold = None
    time_multiplier = None
    tag_data = None
    init_checker_limit_timer = None
    menu_client_cache: dict = {}

    def __init__(self, room_id: RoomID) -> None:
        self.room_id = room_id
        self.message_counter = 0
        self.ignore = False
        self.ignored_counter = 0
        self.time_to_ignore = self.default_time_to_ignore
        self.running_limit_task = False
        self.running_restore_task = False
        self.task_name = f"{room_id}_message_traceback"
        self._is_bot: bool | None = None

    @classmethod
    def init_cls(cls, api, domain, config: Config) -> None:
        cls.api = api
        cls.domain = domain
        cls.default_time_to_ignore = config["menuflow.bot_war.time_to_ignore"]
        cls.ignored_counter_threshold = config["menuflow.bot_war.ignored_counter_threshold"]
        cls.message_threshold = config["menuflow.bot_war.message_threshold"]
        cls.time_multiplier = config["menuflow.bot_war.time_multiplier"]
        cls.tag_data = config["menuflow.bot_war.tag_data"]
        cls.init_checker_limit_timer = config["menuflow.bot_war.init_checker_limit_timer"]

    @classmethod
    def _get_or_create(cls, room_id: RoomID) -> RoomMonitor:
        if room_id not in cls.MONITORING_ROOMS:
            cls.log.debug(f"[{room_id}] Adding room to message traceback")
            cls.MONITORING_ROOMS[room_id] = RoomMonitor(room_id=room_id)
        return cls.MONITORING_ROOMS[room_id]

    async def ignore_room(self) -> bool:
        """
        Run bot-war checks and timers for an incoming message

        Returns True if the message must not be processed further
        """
        monitor = self._get_or_create(self.room_id)

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

    def register_message(self) -> None:
        self._get_or_create(self.room_id).message_counter += 1

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
        bot_mxid = await self._get_current_menu()
        menu_access_token = await self._get_menu_credentials(bot_mxid)
        room_tag = self.tag_data
        try:
            self.log.debug(f"[{self.room_id}] Setting room tag {room_tag.get('tag_text')}...")
            url_path = f"/_matrix/client/v3/rooms/{self.room_id}/state/ik.chat.tag"
            request_response = await self.api.session.put(
                url=f"{self.api.base_url}{url_path}",
                headers={"Authorization": f"Bearer {menu_access_token}"},
                json={
                    "tags": [
                        {
                            "id": room_tag.get("space_room_mxid"),
                            "text": room_tag.get("tag_text"),
                            "color": room_tag.get("tag_color"),
                        }
                    ]
                },
            )
            request_response_json = await request_response.json()
            if request_response_json.get("error"):
                self.log.error(
                    f"[{self.room_id}] Error setting room tag {room_tag.get('tag_text')}: "
                    f"{request_response_json.get('error')}"
                )

            self.log.debug(
                f"[{self.room_id}] Setting portal to space for {room_tag.get('space_room_mxid')}..."
            )
            url_path = f"/_matrix/client/v3/rooms/{room_tag.get('space_room_mxid')}/state/m.space.child/{self.room_id}"
            request_response = await self.api.session.put(
                url=f"{self.api.base_url}{url_path}",
                headers={"Authorization": f"Bearer {menu_access_token}"},
                json={"via": [self.domain], "suggested": False},
            )
            request_response_json = await request_response.json()
            if request_response_json.get("error"):
                self.log.error(
                    f"[{self.room_id}] Error setting portal to space {room_tag.get('space_room_mxid')}: "
                    f"{request_response_json.get('error')}"
                )

        except Exception as error:
            self.log.error(
                f"[{self.room_id}] Error adding portal to tag {room_tag.get('tag_text')} "
                f"or space {room_tag.get('space_room_mxid')}: {error}"
            )

    @classmethod
    async def _fetch_is_bot(cls, room_id: RoomID) -> bool:
        conversation_tags = None
        try:
            conversation_tags = await cls.api.session.get(
                url=f"{cls.api.base_url}/_matrix/client/v3/rooms/{room_id}/state/ik.chat.tag",
                headers={"Authorization": f"Bearer {cls.api.token}"},
            )
        except Exception as error:
            cls.log.error(f"Error checking if the {room_id} is a bot: {error}")

        if conversation_tags:
            tags_payload = await conversation_tags.json()
            bot_tag_text = cls.tag_data["tag_text"]
            tag_list = tags_payload.get("tags", tags_payload) if tags_payload else []
            if tag_list and any(
                (tag.get("tag_text") if isinstance(tag, dict) else tag) == bot_tag_text
                for tag in tag_list
            ):
                return True

        return False

    async def _get_menu_credentials(self, bot_mxid: str) -> dict:
        menu_client = self.menu_client_cache.get(bot_mxid)
        return menu_client.access_token

    async def _get_current_menu(self):
        db_room = await DBRoom.get_by_room_id(self.room_id)
        _pv_scope, _pv_key = ProtectedVars.CURRENT_BOT_MXID.value.split(".", 1)
        bot_mxid = db_room._variables.get(_pv_scope, {}).get(_pv_key)

        return bot_mxid

    @classmethod
    async def is_a_bot(cls, room_id: RoomID) -> bool:
        monitor = cls._get_or_create(room_id)
        if monitor._is_bot is None:
            monitor._is_bot = await cls._fetch_is_bot(room_id)
        return monitor._is_bot

    @classmethod
    async def handle_tag_event(cls, evt: StateEvent) -> None:
        monitor = cls._get_or_create(evt.room_id)
        monitor._is_bot = await cls._fetch_is_bot(evt.room_id)
