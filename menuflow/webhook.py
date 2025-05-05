import json
import logging
from menuflow.menu import MenuClient
from menuflow.room import Room
from mautrix.util.logging import TraceLogger

from menuflow.utils.util import Util
from .db import Webhook as DBWhebhook
from mautrix.types import RoomID
from collections import deque


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
            cls.log.critical(f">>>>>>>>>>Webhooks")

            whebhooks_data = await DBWhebhook.get_all_data()

            cls.log.critical(f">>>>>>>>>>Webhooks data: {whebhooks_data}")

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

    async def remove(self) -> None:
        """
        This function removes the webhook from the database and the cache.
        """
        self._remove_from_cache()
        await self.delete()

    @classmethod
    def validate_webhook_filter(cls, room: Room, filter: str, event_data: dict) -> bool:
        """
        This function validates the webhook filter for a room and checks if the event data
        matches the filter.

        Parameters
        ----------
        room : Room
            The room object.
        filter : str
            The filter to validate.
        event_data : dict
            The event data to check against the filter.

        Returns
        -------
        bool
            Returns True if the event data matches the filter, otherwise False.
        """
        if not room:
            cls.log.debug(f"Room {data.room_id} not found")
            return False

        variables = json.loads(room.route.variables)
        cls.log.critical(f"room.route: {room.route}")
        cls.log.critical(f"room.route.variables: {room.route.variables}")
        cls.log.critical(f"room.route.variables type: {type(variables)}")
        cls.log.critical(f"event_data: {event_data}")

        if not room.route or not "filter" in variables.keys():
            cls.log.debug(f"Room {room.room_id} does not have a route filter")
            return False

        # Check if the room is waiting for a webhook event validating the filter
        jq_result: dict = Util.jq_compile(filter=filter, json_data=event_data)

        cls.log.critical(f"JQ result: {jq_result}")

        if jq_result.get("status") != 200:
            cls.log.error(
                f"""Error parsing '{filter}' with jq on variable '{event_data}'.
                Error message: {jq_result.get("error")}, Status: {jq_result.get("status")}
                Room_id: {room.room_id}, Client: {room.client}
                """
            )
            return False

        return True

    @classmethod
    async def handle_webhook_event(cls, event: dict) -> None:
        """
        This function handles the webhook event and executes the flow in the rooms that are
        waiting for it.

        Parameters
        ----------
        event : dict
            The webhook event data.

        Returns
        -------
        None
            This function does not return anything.
        """
        cls.log.debug(f"Incoming webhook event: {event}")

        # Get the data from rooms that waiting for webhook event
        whebhook_data = await cls.get_whebhook_data()

        cls.log.critical(f"Webhook data: {whebhook_data}")

        if not whebhook_data:
            cls.log.debug("No rooms waiting for webhook event")
            return

        webhooks_to_delete = deque()

        for whebhook in whebhook_data.values():
            room = await Room.get_by_room_id(room_id=whebhook.room_id, bot_mxid=whebhook.client)

            cls.log.critical(
                f"Webhook data: {whebhook.room_id} - {whebhook.client} - {whebhook.filter}"
            )
            cls.log.critical(f"Event data: {event}")

            if not cls.validate_webhook_filter(
                room=room, filter=whebhook.filter, event_data=event
            ):
                cls.log.debug(
                    f"Webhook filter does not match for room {room.room_id} and event {event}"
                )
                continue

            cls.log.debug(f"Executing event for room {room.room_id}")
            menu_client = await MenuClient.get(user_id=whebhook.client)

            if not menu_client:
                cls.log.debug(f"Menu client not found for room {room.room_id}")
                continue

            # Get the node of the room
            node = menu_client.matrix_handler.flow.node(room=room)

            cls.log.critical(f"Node: {node}")

            if not node:
                cls.log.debug(f"Node not found for room {room.room_id}")
            # TODO: Check if the node is a webhook node
            # Execute event to the flow

            webhooks_to_delete.append(whebhook)

        cls.log.critical(f"Webhooks to delete: {webhooks_to_delete}")
        # Remove the webhooks that are not needed anymore
        while webhooks_to_delete:
            webhook = webhooks_to_delete.popleft()
            cls.log.critical(f"Removing webhook: {webhook}")
            cls.log.debug(f"Removing webhook for room {webhook.room_id}")
            await webhook.remove()
