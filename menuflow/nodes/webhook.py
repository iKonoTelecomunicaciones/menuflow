import json
from enum import Enum
from time import time
from typing import Any

from markdown import markdown
from mautrix.types import Format, MessageEvent, MessageType, TextMessageEventContent

from menuflow.db.route import RouteState
from menuflow.events.event_types import MenuflowNodeEvents
from menuflow.room import Room
from menuflow.utils.types import Nodes
from menuflow.utils.util import Util
from menuflow.webhook.webhook_queue import WebhookQueue

from ..repository import Webhook as WebhookModel
from ..webhook.webhook import Webhook as ControllerWebhook
from .input import Input


class WebhookCase(Enum):
    WEBHOOK = "webhook"


class Webhook(Input):
    def __init__(self, webhook_data: WebhookModel, room: Room, default_variables: dict) -> None:
        Input.__init__(
            self, input_node_data=webhook_data, room=room, default_variables=default_variables
        )
        self.log = self.log.getChild(webhook_data.get("id"))
        self.content: WebhookModel = webhook_data
        self.webhook_queue: WebhookQueue = WebhookQueue(
            config=self.room.config, trace_id=self.room.room_id
        )

    @property
    def filter(self) -> str:
        """
        This property returns the filter for the webhook.

        Returns
        -------
        str
            The filter for the webhook.
        """
        return self.render_data(self.content.get("filter"))

    @property
    def variables(self) -> dict[str, Any]:
        """
        This property returns the variables for the webhook.

        Returns
        -------
        dict[str, Any]
            The variables for the webhook.
        """
        return self.render_data(self.content.get("variables"))

    def reserved_cases(self) -> set[str]:
        return super().reserved_cases() | {case.value for case in WebhookCase}

    async def get_webhook(self, filter: str) -> ControllerWebhook:
        """
        This function gets the webhook data from the database and returns it.

        Returns
        -------
        ControllerWebhook
            The webhook data.
        """
        webhook = await ControllerWebhook.get_by_room_id_and_client(
            room_id=self.room.room_id, client=self.room.matrix_client.mxid
        )

        if not webhook:
            self.log.debug(f"[{self.room.room_id}] Webhook not found, Creating webhook...")
            return await self._save_webhook(filter=filter)

        if webhook.filter != filter:
            self.log.debug(
                f"[{self.room.room_id}] Replacing webhook filter "
                f"{webhook.filter} with {filter}"
            )
            await webhook.remove()
            return await self._save_webhook(filter=filter)

        return webhook

    async def _save_webhook(self, filter: str) -> ControllerWebhook:
        return await ControllerWebhook.save_webhook(
            room_id=self.room.room_id,
            client=self.room.matrix_client.mxid,
            filter=filter,
            subscription_time=int(time()),
        )

    async def _remove_subscription(self) -> None:
        """Delete the room subscription when it exists, without creating one."""
        webhook = await ControllerWebhook.get_by_room_id_and_client(
            room_id=self.room.room_id, client=self.room.matrix_client.mxid
        )
        if not webhook:
            return

        self.log.debug(f"[{self.room.room_id}] Deleting webhook from db")
        await webhook.remove()

    async def _handle_user_message(self, evt: MessageEvent) -> None:
        o_connection = None
        if evt.content.body.lower() != WebhookCase.WEBHOOK.value:
            o_connection = await self.input_text(text=evt.content.body)

        if o_connection:
            await self._remove_subscription()
        else:
            if _fail_msg := self.validation_fail_message:
                msg_content = TextMessageEventContent(
                    msgtype=MessageType.TEXT,
                    body=_fail_msg,
                    format=Format.HTML,
                    formatted_body=markdown(text=_fail_msg, extensions=["nl2br"]),
                )
                await self.send_message(self.room.room_id, msg_content)
            await self.room.update_menu(
                node_id=self.id, state=RouteState.INPUT, update_node_vars=False
            )

        await self._send_node_event(o_connection=None, event_type=MenuflowNodeEvents.NodeInputData)

    async def management_webhook(self, evt: dict) -> str | None:
        """
        This function manages the webhook event for the webhook.
        Set the variables for the webhook and update the menu for the room.

        Parameters
        ----------
        evt : dict
            The event data.

        Returns
        -------
        str | None
            The connection data for the webhook.
            If the event is not valid, it returns None.
        """
        variables = self.resolve_response_variables(self.variables, evt)

        if variables:
            await self.room.set_variables(variables=variables)

        o_connection = await self.get_case_by_id(WebhookCase.WEBHOOK.value)
        if o_connection:
            await self.room.update_menu(o_connection)

        await self._send_node_event(
            o_connection=o_connection, event_type=MenuflowNodeEvents.NodeInputData
        )

        return o_connection

    async def search_enqueue_events(self, webhook_filter: str) -> WebhookQueue | None:
        """
        This function searches for events in the webhook queue and manages them if they match
        the filter.

        Parameters
        ----------
        webhook_filter : str
            The rendered filter to match against queued events.

        Returns
        -------
        WebhookQueue | None
            A WebhookQueue object that matches the filter.
            If no events match, None is returned.
        """
        events = await self.webhook_queue.get_events_from_db()
        _room_id = self.room.room_id
        if not events:
            self.log.debug(f"[{_room_id}] No events found in the webhook queue")
            return None

        self.log.debug(
            f"[{_room_id}] Webhook queue has {len(events)} events, searching for matches..."
        )
        event_to_managed = None
        for event in events:
            try:
                dict_event = json.loads(event.event)
            except json.JSONDecodeError:
                continue

            if not self.validate_webhook_filter(filter=webhook_filter, event_data=dict_event):
                continue

            self.log.debug(
                f"[{_room_id}] Webhook filter {webhook_filter} matched with event: {event}"
            )

            event_to_managed = event
            break

        return event_to_managed

    async def _manage_queued_event(self, event: WebhookQueue) -> None:
        self.log.debug(f"[{self.room.room_id}] Event ID {event.id} managed from queue")
        try:
            await self.management_webhook(evt=json.loads(event.event))
        except json.JSONDecodeError:
            self.log.error(
                f"[{self.room.room_id}] Error decoding JSON for event ID {event.id}. "
                f"Event data: {event.event}"
            )

    async def run(self, evt: dict | MessageEvent | None) -> dict:
        """
        This function runs the webhook and sends the event data to the webhook URL.
        It also checks if the event data matches the filter for the webhook.
        Parameters
        ----------
        evt : dict | None
            The event data to send to the webhook.
            If None, the function will not send any data to the webhook.

        """
        if self.room.route.state == RouteState.TIMEOUT:
            await self._remove_subscription()
            await self._handle_input_timeout()
            return

        _filter = self.filter

        if self.room.route.state == RouteState.INPUT:
            if not isinstance(evt, dict) and (queued := await self.search_enqueue_events(_filter)):
                await self._remove_subscription()
                await self._manage_queued_event(queued)
                return

            if isinstance(evt, MessageEvent):
                await self._handle_user_message(evt)
            else:
                await self.management_webhook(evt=evt)
            return

        if event_to_manage := await self.search_enqueue_events(_filter):
            await self._manage_queued_event(event_to_manage)
            return

        self.log.debug(f"[{self.room.room_id}] Entering webhook node {self.id}")
        await self.get_webhook(filter=_filter)

        # An event may have been stored while the subscription was being created.
        if event_to_manage := await self.search_enqueue_events(_filter):
            await self._remove_subscription()
            await self._manage_queued_event(event_to_manage)
            return

        await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)
        await self._send_node_event(
            o_connection=None, event_type=MenuflowNodeEvents.NodeEntry, node_type=Nodes.webhook
        )

    def validate_webhook_filter(self, filter: str, event_data: dict) -> bool:
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
        webhook_filter = self.filter
        filter_db = self.render_data(filter)
        _room_id = self.room.room_id

        if not webhook_filter:
            self.log.debug(f"[{self.room.room_id}] Webhook does not have a route filter")
            return False

        if not webhook_filter == filter_db:
            self.log.debug(
                f"[{_room_id}] Webhook filter does not match "
                f"Webhook filter: {webhook_filter} Filter from db in webhook node: {filter} "
            )
            return False

        # Check if the room is waiting for a webhook event validating the filter
        jq_result: dict = Util.jq_compile(filter=webhook_filter, json_data=event_data)

        if jq_result.get("status") != 200:
            self.log.error(
                f"[{_room_id}] Error parsing '{filter}' with jq on variable '{event_data}'. "
                f"Error message: {jq_result.get('error')}, Status: {jq_result.get('status')}"
            )
            return False

        if not jq_result.get("result")[0]:
            self.log.debug(
                f"[{_room_id}] Webhook filter does not match the event data "
                f"Webhook filter: {webhook_filter} Event data: {event_data}"
            )
            return False

        return True
