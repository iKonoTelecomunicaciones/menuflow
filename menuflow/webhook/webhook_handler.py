import logging
from collections import deque
from copy import deepcopy

from mautrix.types import RoomID
from mautrix.util.logging import TraceLogger

from menuflow.menu import MenuClient
from menuflow.room import Room
from menuflow.web.base import get_config

from .webhook import Webhook
from .webhook_queue import WebhookQueue


class WebhookHandler:
    log: TraceLogger = logging.getLogger("menuflow.handler_webhook")
    webhook_queue: WebhookQueue = None

    def __init__(self, trace_id: str) -> None:
        self.webhook_queue = WebhookQueue(config=get_config(), trace_id=trace_id)
        self.trace_id = trace_id

    async def _remove_webhooks(self, webhooks: list[Webhook]) -> None:
        """
        This function removes the webhooks from the database.

        Parameters
        ----------
        webhooks : list[Webhook]
            The webhooks to remove.
        """
        while webhooks:
            webhook = webhooks.popleft()
            self.log.debug(f"({self.trace_id}) Removing webhook for room {webhook.room_id}")
            await webhook.remove()

    async def handle_webhook_event(self, event: dict) -> tuple[int, str]:
        """
        This function handles the webhook event and executes the flow in the rooms that are
        waiting for it.

        Parameters
        ----------
        event : dict
            The webhook event data.

        Returns
        -------
        tuple[int, str]
            A tuple containing the status code and a message.
            The status code is 200 if the event was handled successfully, otherwise it is 422.
            The message is a string describing the result of the operation.
        """
        self.log.debug(f"({self.trace_id}) Incoming new webhook event: {event}")

        # Get the data from rooms that waiting for webhook event
        whebhook_data: dict[RoomID, Webhook] | None = await Webhook.get_webhook_data()

        if not whebhook_data:
            self.log.debug(
                f"({self.trace_id}) No rooms waiting for webhook event, saving to queue"
            )
            event_id = await self.webhook_queue.get_event_id(event=event)

            if event_id is not None:
                await self.webhook_queue.add_event_to_queue(event=event, event_id=event_id)

            return 202, "Webhook event saved to queue, no rooms waiting"

        whebhook_data_copy = deepcopy(whebhook_data)
        webhooks_to_delete = deque()

        message = "The event was not handled successfully"
        status = 202

        for whebhook in whebhook_data_copy.values():
            room: Room | None = await Room.get_by_room_id(room_id=whebhook.room_id)
            if not room:
                webhooks_to_delete.append(whebhook)
                self.log.debug(f"({self.trace_id}) Room {whebhook.room_id} not found")
                continue

            menu_client: MenuClient | None = await MenuClient.get(user_id=whebhook.client)

            if not menu_client:
                webhooks_to_delete.append(whebhook)
                self.log.debug(f"({self.trace_id}) Menu client not found for room {room.room_id}")
                continue

            # Get the node of the room
            node = menu_client.matrix_handler.flow.node(room=room)

            if not node:
                webhooks_to_delete.append(whebhook)
                self.log.debug(f"({self.trace_id}) Node webhook not found for room {room.room_id}")
                message = "Node webhook not found in rooms"
                continue

            if not node.type or node.type != "webhook":
                webhooks_to_delete.append(whebhook)
                self.log.debug(
                    f"({self.trace_id}) Node is not a webhook node for room {room.room_id}"
                )
                message = "No rooms with webhook node found"
                continue

            if not node.validate_webhook_filter(filter=whebhook.filter, event_data=event):
                self.log.debug(
                    f"({self.trace_id}) Webhook filter {whebhook.filter} "
                    f"does not match for room {room.room_id} and event {event}"
                )
                message = f"Webhook filter {whebhook.filter} does not match for event {event}"
                continue

            delivered = menu_client.matrix_handler.deliver_webhook_event(
                room_id=room.room_id, event=event
            )
            if not delivered:
                self.log.debug(
                    f"({self.trace_id}) Webhook event not delivered for room {room.room_id}"
                )
                continue

            self.log.debug(f"({self.trace_id}) Executing event for room {room.room_id}")
            status = 200
            message = "The event was handled successfully"
            webhooks_to_delete.append(whebhook)

        if webhooks_to_delete:
            await self._remove_webhooks(webhooks=webhooks_to_delete)

        if status != 200:
            self.log.debug(f"({self.trace_id}) Event data not handled, saving to queue")
            event_id = await self.webhook_queue.get_event_id(event=event)

            if event_id is not None:
                await self.webhook_queue.add_event_to_queue(event=event, event_id=event_id)

            return status, message

        queued_event = await self.webhook_queue.get_event(event=event)
        if queued_event:
            self.log.debug(
                f"({self.trace_id}) Event data handled successfully, removing event from queue"
            )
            await self.webhook_queue.remove_event_from_queue(id=queued_event.id)

        return status, message
