import logging

from menuflow.menu import MenuClient
from menuflow.room import Room
from mautrix.util.logging import TraceLogger
from mautrix.types import RoomID

from collections import deque

from .webhook import Webhook

class WebhookHandler():
    log: TraceLogger = logging.getLogger("menuflow.handler_webhook")

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
        whebhook_data: dict[RoomID, Webhook] | None = await Webhook.get_whebhook_data()

        if not whebhook_data:
            cls.log.debug("No rooms waiting for webhook event")
            return

        webhooks_to_delete = deque()

        for whebhook in whebhook_data.values():
            room = await Room.get_by_room_id(room_id=whebhook.room_id, bot_mxid=whebhook.client)
            menu_client = await MenuClient.get(user_id=whebhook.client)

            if not menu_client:
                webhooks_to_delete.append(whebhook)
                cls.log.debug(f"Menu client not found for room {room.room_id}")
                continue

            # Get the node of the room
            node = menu_client.matrix_handler.flow.node(room=room)

            if not node:
                webhooks_to_delete.append(whebhook)
                cls.log.debug(f"Node not found for room {room.room_id}")
                continue

            if not node.id or node.id != "webhook_node":
                webhooks_to_delete.append(whebhook)
                cls.log.debug(f"Node is not a webhook node for room {room.room_id}")
                continue

            if not node.validate_webhook_filter(
                 filter=whebhook.filter, event_data=event
            ):
                cls.log.debug(
                    f"Webhook filter {whebhook.filter} does not match for room {room.room_id} and event {event}"
                )
                continue

            cls.log.debug(f"Executing event for room {room.room_id}")

            # Execute event to the flow
            await node.run(evt=event)
            webhooks_to_delete.append(whebhook)

        # Remove the webhooks that are not needed anymore
        while webhooks_to_delete:
            webhook = webhooks_to_delete.popleft()
            cls.log.debug(f"Removing webhook for room {webhook.room_id}")
            await webhook.remove()