from __future__ import annotations

import logging

from mautrix.types import RoomID, UserID
from mautrix.util.logging import TraceLogger

from ..db import Webhook as DBWhebhook


class Webhook(DBWhebhook):
    by_room_id: dict[RoomID, "Webhook"] = {}
    log: TraceLogger = logging.getLogger("menuflow.webhook")

    def __init__(
        self, room_id: RoomID, client: str, filter: str, subscription_time: int, id: int = None
    ) -> None:
        super().__init__(
            id=id,
            room_id=room_id,
            client=client,
            filter=filter,
            subscription_time=subscription_time,
        )
        self.by_room_id[room_id] = self

    def _add_to_cache(self) -> None:
        """
        This function adds the webhook to the cache by adding it to the `by_room_id`
        dictionary using the room ID as the key. If the room ID is already in the cache,
        it updates the existing entry with the new webhook data.
        """
        if self.room_id:
            self.by_room_id[self.room_id] = self

    def _remove_from_cache(self) -> None:
        """
        This function removes the webhook from the cache by deleting it from the
        `by_room_id` dictionary using the room ID as the key.
        If the room ID is not found in the cache, it does nothing.
        """
        if self.room_id in self.by_room_id:
            del self.by_room_id[self.room_id]

    @classmethod
    async def get_whebhook_data(cls) -> dict[RoomID, "Webhook"] | None:
        """
        This function retrieves all the webhook data from the database and caches it in the
        `by_room_id` dictionary. If the data is already cached, it returns the cached data.
        If the data is not cached, it fetches the data from the database and caches it.

        Returns
        -------
        dict[RoomID, Webhook] | None
            Returns a dictionary of webhook data indexed by room ID. If no data is found,
            returns None.
        """
        if not cls.by_room_id:
            whebhooks_data = await DBWhebhook.get_all_data()

            if isinstance(whebhooks_data, list) and len(whebhooks_data) > 0:
                for whebhook_data in whebhooks_data:
                    whebhook = cls(
                        whebhook_data.room_id,
                        whebhook_data.client,
                        whebhook_data.filter,
                        whebhook_data.subscription_time,
                    )
                    cls.by_room_id[whebhook.room_id] = whebhook

        return cls.by_room_id

    @classmethod
    async def get_by_room_id_and_client(cls, room_id: RoomID, client: UserID) -> "Webhook" | None:
        """
        This function retrieves the webhook data for a specific room ID and client ID from the
        cache or database.

        If the data is not found in the cache, it fetches the data from the database and caches it.

        Parameters
        ----------
        room_id : RoomID
            The room ID to retrieve the webhook data for.
        client : UserID
            The client ID of the menu client.

        Returns
        -------
        Webhook | None
            Returns the webhook data for the specified room ID and client ID. If no data is found,
            returns None.
        """
        try:
            return cls.by_room_id[room_id]
        except KeyError:
            pass

        webhook = await cls.get_by_room_id(room_id=room_id, client=client)

        if not webhook:
            cls.log.debug(f"Webhook not found from room {room_id} and client {client}")
            return None

        cls.log.debug(f"Webhook found from room {room_id} and client {client}")
        cls.by_room_id[room_id] = webhook
        return webhook

    @classmethod
    async def save_webhook(
        cls, room_id: RoomID, client: UserID, filter: str, subscription_time: int
    ) -> "Webhook":
        """
        This function saves the webhook data to the database and adds it to the cache.

        Parameters
        ----------
        room_id : RoomID
            The room ID to save the webhook data for.
        client : UserID
            The client ID of the menu client.
        filter : str
            The filter string for the webhook.
        subscription_time : int
            The subscription time for the webhook.

        Returns
        -------
        Webhook
            Returns the saved webhook data.
        """
        webhook = cls(room_id, client, filter, subscription_time)
        await webhook.insert()
        webhook._add_to_cache()
        return webhook

    async def remove(self) -> None:
        """
        This function removes the webhook from the database and the cache.
        """
        self._remove_from_cache()
        await self.delete()
