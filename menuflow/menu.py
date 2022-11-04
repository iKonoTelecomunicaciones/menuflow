from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, AsyncGenerator, Awaitable, Callable, cast

from aiohttp import ClientSession
from mautrix.client import Client, InternalEventType
from mautrix.errors import MatrixInvalidToken
from mautrix.types import (
    DeviceID,
    EventFilter,
    EventType,
    Filter,
    FilterID,
    RoomEventFilter,
    RoomFilter,
    StateFilter,
    SyncToken,
    UserID,
)
from mautrix.util.async_getter_lock import async_getter_lock
from mautrix.util.logging import TraceLogger

import menuflow

from .db import Client as DBClient
from .jinja.jinja_template import FILTERS
from .matrix import MatrixHandler

if TYPE_CHECKING:
    from .__main__ import MenuFlow


class MenuClient(DBClient):
    menuflow: "MenuFlow" = None
    cache: dict[UserID, Client] = {}
    _async_get_locks: dict[Any, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())
    log: TraceLogger = logging.getLogger("menuflow.client")

    http_client: ClientSession = None

    matrix_handler: MatrixHandler
    started: bool

    def __init__(
        self,
        id: UserID,
        homeserver: str,
        access_token: str,
        device_id: DeviceID,
        next_batch: SyncToken = "",
        filter_id: FilterID = "",
        autojoin: bool = True,
    ) -> None:
        super().__init__(
            id=id,
            homeserver=homeserver,
            access_token=access_token,
            device_id=device_id,
            next_batch=next_batch,
            filter_id=filter_id,
            autojoin=bool(autojoin),
        )
        self._postinited = False

    @classmethod
    def init_cls(cls, menuflow: "MenuFlow") -> None:
        cls.menuflow = menuflow

    def _make_client(
        self, homeserver: str | None = None, token: str | None = None, device_id: str | None = None
    ) -> MatrixHandler:
        return MatrixHandler(
            config=self.menuflow.config,
            mxid=self.id,
            base_url=homeserver or self.homeserver,
            token=token or self.access_token,
            client_session=self.http_client,
            log=self.log,
            crypto_log=self.log.getChild("crypto"),
            loop=self.menuflow.loop,
            device_id=device_id or self.device_id,
            sync_store=self,
            # state_store=self.menuflow.state_store,
        )

    def postinit(self) -> None:
        if self._postinited:
            raise RuntimeError("postinit() called twice")
        self._postinited = True
        self.cache[self.id] = self
        self.log = self.log.getChild(self.id)
        self.http_client = ClientSession(loop=self.menuflow.loop)
        self.started = False
        self.sync_ok = True
        self.matrix_handler = self._make_client()
        # if self.enable_crypto:
        #     self._prepare_crypto()
        # else:
        #     self.crypto_store = None
        #     self.crypto = None
        self.matrix_handler.ignore_initial_sync = True
        self.matrix_handler.ignore_first_sync = True
        if self.autojoin:
            self.matrix_handler.add_event_handler(
                EventType.ROOM_MEMBER, self.matrix_handler.handle_invite
            )

        self.matrix_handler.add_event_handler(
            EventType.ROOM_MESSAGE, self.matrix_handler.handle_message
        )
        self.matrix_handler.add_event_handler(
            InternalEventType.SYNC_ERRORED, self._set_sync_ok(False)
        )
        self.matrix_handler.add_event_handler(
            InternalEventType.SYNC_SUCCESSFUL, self._set_sync_ok(True)
        )

    def _set_sync_ok(self, ok: bool) -> Callable[[dict[str, Any]], Awaitable[None]]:
        async def handler(data: dict[str, Any]) -> None:
            pass

        return handler

    async def start(self, try_n: int | None = 0) -> None:
        try:
            if try_n > 0:
                await asyncio.sleep(try_n * 10)
            await self._start(try_n)
        except Exception:
            self.log.exception("Failed to start")

    async def _start(self, try_n: int | None = 0) -> None:
        if self.started:
            self.log.warning("Ignoring start() call to started client")
            return
        try:
            await self.matrix_handler.versions()
            whoami = await self.matrix_handler.whoami()
        except MatrixInvalidToken as e:
            self.log.error(f"Invalid token: {e}. Disabling client")
            self.enabled = False
            await self.update()
            return
        except Exception as e:
            if try_n >= 8:
                self.log.exception("Failed to get /account/whoami, disabling client")
                self.enabled = False
                await self.update()
            else:
                self.log.warning(
                    f"Failed to get /account/whoami, retrying in {(try_n + 1) * 10}s: {e}"
                )
                _ = asyncio.create_task(self.start(try_n + 1))
            return
        if whoami.user_id != self.id:
            self.log.error(f"User ID mismatch: expected {self.id}, but got {whoami.user_id}")
            self.enabled = False
            await self.update()
            return
        elif whoami.device_id and self.device_id and whoami.device_id != self.device_id:
            self.log.error(
                f"Device ID mismatch: expected {whoami.device_id}, but got {self.device_id}"
            )
            self.enabled = False
            await self.update()
            return
        if not self.filter_id:
            self.filter_id = await self.matrix_handler.create_filter(
                Filter(
                    room=RoomFilter(
                        timeline=RoomEventFilter(
                            limit=50,
                            lazy_load_members=True,
                        ),
                        state=StateFilter(
                            lazy_load_members=True,
                        ),
                    ),
                    presence=EventFilter(
                        not_types=[EventType.PRESENCE],
                    ),
                )
            )
            await self.update()
        # if self.crypto:
        #     await self._start_crypto()
        self.start_sync()
        self.started = True
        self.log.info("Client started")
        self.matrix_handler.config = self.menuflow.config

    def start_sync(self) -> None:
        self.matrix_handler.start(self.filter_id)

    def stop_sync(self) -> None:
        self.matrix_handler.stop()

    async def stop(self) -> None:
        if self.started:
            self.started = False
            self.stop_sync()

    async def clear_cache(self) -> None:
        self.stop_sync()
        self.filter_id = FilterID("")
        self.next_batch = SyncToken("")
        await self.update()
        self.start_sync()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "homeserver": self.homeserver,
            "access_token": self.access_token,
            "device_id": self.device_id,
            # "fingerprint": (
            #     self.crypto.account.fingerprint if self.crypto and self.crypto.account else None
            # ),
            "autojoin": self.autojoin,
        }

    async def delete(self) -> None:
        try:
            del self.cache[self.id]
        except KeyError:
            pass
        await super().delete()

    @classmethod
    async def all(cls) -> AsyncGenerator[MenuClient, None]:
        users = await super().all()
        user: cls
        for user in users:
            try:
                yield cls.cache[user.id]
            except KeyError:
                user.postinit()
                yield user

    @classmethod
    @async_getter_lock
    async def get(
        cls,
        user_id: UserID,
        *,
        homeserver: str | None = None,
        access_token: str | None = None,
        device_id: DeviceID | None = None,
    ) -> Client | None:
        try:
            return cls.cache[user_id]
        except KeyError:
            pass

        user = cast(cls, await super().get(user_id))
        if user is not None:
            user.postinit()
            return user

        if homeserver and access_token:
            user = cls(
                user_id,
                homeserver=homeserver,
                access_token=access_token,
                device_id=device_id or "",
            )
            await user.insert()
            user.postinit()
            return user

        return None
