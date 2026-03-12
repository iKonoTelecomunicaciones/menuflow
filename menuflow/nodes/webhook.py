import json
from time import time
from typing import Any

from markdown import markdown
from mautrix.types import Format, MessageEvent, MessageType, TextMessageEventContent

from menuflow.db.route import RouteState
from menuflow.events.event_generator import send_node_event
from menuflow.events.event_types import MenuflowNodeEvents
from menuflow.room import Room
from menuflow.utils.types import Nodes, NodeStatus
from menuflow.utils.util import Util
from menuflow.webhook.webhook_queue import WebhookQueue

from ..repository import Webhook as WebhookModel
from ..webhook.webhook import Webhook as ControllerWebhook
from .input import Input


class Webhook(Input):
    def __init__(self, webhook_data: WebhookModel, room: Room, default_variables: dict) -> None:
        Input.__init__(
            self, input_node_data=webhook_data, room=room, default_variables=default_variables
        )
        self.log = self.log.getChild(webhook_data.get("id"))
        self.content: WebhookModel = webhook_data
        self.webhook_queue: WebhookQueue = WebhookQueue(config=self.room.config)

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

    async def get_webhook(self) -> ControllerWebhook:
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
            self.log.debug(f"Webhook not found for room {self.room.room_id}")
            self.log.debug("Creating webhook...")
            webhook = await ControllerWebhook.save_webhook(
                room_id=self.room.room_id,
                client=self.room.matrix_client.mxid,
                filter=self.filter,
                subscription_time=int(time()),
            )

        return webhook

    async def send_node_event(
        self,
        o_connection: str | None,
        event_type: MenuflowNodeEvents,
        node_type: Nodes | None = None,
    ) -> None:
        """
        This function sends a node event to the room with the webhook data.
        It also updates the menu for the room.
        Parameters
        ----------
        o_connection : str | None
            The connection data for the webhook.

        """
        if o_connection:
            await self.room.update_menu(o_connection)

        _variables = None
        if event_type != MenuflowNodeEvents.NodeEntry:
            _variables = self.room.all_variables | self.default_variables

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=event_type,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=node_type,
            node_id=self.id,
            o_connection=o_connection,
            variables=_variables,
            conversation_uuid=self.room.conversation_uuid,
        )

    async def management_message(self, evt: dict, webhook: ControllerWebhook) -> None:
        """
        This function manages the message event for the webhook.
        It checks if the event is from a user message and validates if the message corresponds to the
        cancel webhook cases.

        Parameters
        ----------
        evt : dict
            The event data.
        """
        o_connection = None

        if evt.content.body.lower() != NodeStatus.WEBHOOK.value:
            o_connection = await self.input_text(text=evt.content.body)

        if o_connection:
            self.log.debug(f"Deleting webhook from db: {self.room.room_id}")
            await webhook.remove()
        else:
            if self.validation_fail_message:
                msg_content = TextMessageEventContent(
                    msgtype=MessageType.TEXT,
                    body=self.validation_fail_message,
                    format=Format.HTML,
                    formatted_body=markdown(
                        text=self.validation_fail_message, extensions=["nl2br"]
                    ),
                )
                await self.send_message(self.room.room_id, msg_content)

            inactivity = self.inactivity_options
            if inactivity.get("active"):
                await self.timeout_active_chats(inactivity)

        await self.send_node_event(o_connection=None, event_type=MenuflowNodeEvents.NodeInputData)

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
        variables = await self.set_webhook_variables(data=evt)

        if variables:
            await self.room.set_variables(variables=variables)

        o_connection = await self.get_case_by_id(NodeStatus.WEBHOOK.value)
        await self.send_node_event(
            o_connection=o_connection, event_type=MenuflowNodeEvents.NodeInputData
        )

        if o_connection:
            self.log.debug(f"Cancelling waiting task for room {self.room.room_id} in webhook node")
            await Util.cancel_task(task_name=self.room.room_id)

        return o_connection

    async def search_enqueue_events(self, webhook: ControllerWebhook) -> WebhookQueue | None:
        """
        This function searches for events in the webhook queue and manages them if they match
        the filter.

        Parameters
        ----------
        webhook : ControllerWebhook
            The webhook data to search for events.

        Returns
        -------
        WebhookQueue | None
            A WebhookQueue object that matches the filter.
            If no events match, None is returned.
        """
        events = await self.webhook_queue.get_events_from_db()
        if not events:
            self.log.debug(f"No events found in the webhook queue for room {self.room.room_id}")
            return None

        self.log.debug(f"Webhook queue has {len(events)} events, searching for matches...")
        event_to_managed = None
        for event in events:
            try:
                dict_event = json.loads(event.event)
            except json.JSONDecodeError:
                continue

            if not self.validate_webhook_filter(filter=webhook.filter, event_data=dict_event):
                continue

            self.log.debug(
                f"Webhook filter {webhook.filter} matched for room {self.room.room_id} with event: {event}"
            )

            event_to_managed = event
            break

        return event_to_managed

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
        webhook: ControllerWebhook = await self.get_webhook()

        if event_to_manage := await self.search_enqueue_events(webhook):
            self.log.debug(f"Managed {event_to_manage.id} from queue")

            try:
                await self.management_webhook(evt=json.loads(event_to_manage.event))
            except json.JSONDecodeError:
                self.log.error(
                    f"Error decoding JSON for event {event_to_manage.id}. "
                    f"Event: {event_to_manage.event}"
                )

            return

        # Webhook endpoint entry execution
        if not isinstance(evt, MessageEvent) and self.room.route.state == RouteState.INPUT:
            await self.management_webhook(evt=evt)
            await Util.cancel_task(task_name=self.room.room_id)
            return

        if self.room.route.state != RouteState.INPUT:
            await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)

            await self.send_node_event(
                o_connection=None,
                event_type=MenuflowNodeEvents.NodeEntry,
                node_type=Nodes.webhook,
            )

            inactivity = self.inactivity_options
            if inactivity.get("active") and not Util.get_tasks_by_name(
                task_name=self.room.room_id
            ):
                if not inactivity.get("chat_timeout") or inactivity.get("chat_timeout") <= 0:
                    self.log.debug(
                        f"Chat timeout is not set in node webhook for room: {self.room.room_id}"
                    )
                    return
                await self.timeout_active_chats(inactivity)

                self.log.debug(f"Deleting webhook from db: {self.room.room_id}")
                await webhook.remove()

            return

        if isinstance(evt, MessageEvent):
            await self.management_message(evt=evt, webhook=webhook)

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

        if not webhook_filter:
            self.log.debug(f"[{self.room.room_id}] Webhook does not have a route filter")
            return False

        if not webhook_filter == filter_db:
            self.log.debug(
                f"Webhook filter does not match the filter for room {self.room.room_id}"
                f"Webhook filter for room {self.room.room_id}: {webhook_filter}"
                f"Filter from db in webhook node for {self.room.room_id}: {filter}"
            )
            return False

        # Check if the room is waiting for a webhook event validating the filter
        jq_result: dict = Util.jq_compile(filter=webhook_filter, json_data=event_data)

        if jq_result.get("status") != 200:
            self.log.error(
                f"Error parsing '{filter}' with jq on variable '{event_data}'. "
                f"Error message: {jq_result.get('error')}, Status: {jq_result.get('status')}"
                f"Room_id: {self.room.room_id}"
            )
            return False

        if not jq_result.get("result")[0]:
            self.log.debug(
                f"Webhook filter does not match the event data for room {self.room.room_id}"
                f"Webhook filter: {webhook_filter}"
                f"Event data: {event_data}"
            )
            return False

        return True

    def validate_jq_data(self, data: dict, variable: dict, default_value: dict) -> dict:
        """
        This function validates the jq data for the webhook.

        Parameters
        ----------
        data : dict
            The JSON data to validate.
        variable : dict
            The variable to validate.
        default_value : dict
            The default value to use if the validation fails.

        Returns
        -------
        dict
            The validated jq data.
        """
        jq_result: dict = Util.jq_compile(self.variables[variable], data)
        if jq_result.get("status") != 200:
            self.log.error(
                f"Error parsing '{self.variables[variable]}' with jq "
                f"on variable '{variable}'. Set to default value ({default_value}). "
                f"Error message: {jq_result.get('error')}, Status: {jq_result.get('status')}"
            )
        return jq_result.get("result")

    async def set_webhook_variables(self, data: dict):
        """
        This function sets the variables for the webhook.

        Parameters
        ----------
        data : dict
            The data to set as variables.
        """
        variables = {}

        if not isinstance(data, (dict, list, str)) and not self.variables:
            return variables

        for variable in self.variables:
            if isinstance(data, str):
                try:
                    variables[variable] = self.render_data(data)
                except KeyError:
                    pass
                break

            default_value = self.default_variables.get("flow").get("jq_default_value")

            data_match = self.validate_jq_data(
                data=data,
                variable=variable,
                default_value=None,
            )

            try:
                data_match = default_value if not data_match else data_match
                variables[variable] = (
                    data_match if not data_match or len(data_match) > 1 else data_match[0]
                )
            except KeyError:
                pass

        return variables
