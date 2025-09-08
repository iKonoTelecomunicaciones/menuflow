import asyncio
import json
from datetime import datetime
from time import time
from typing import Any

from markdown import markdown
from mautrix.types import Format, MessageEvent, MessageType, TextMessageEventContent

from menuflow.db.route import RouteState
from menuflow.events.event_generator import send_node_event
from menuflow.events.event_types import MenuflowNodeEvents
from menuflow.room import Room
from menuflow.utils.types import Nodes
from menuflow.utils.util import Util
from menuflow.webhook.webhook_queue import WebhookQueue

from ..repository import Webhook as WebhookModel
from ..webhook.webhook import Webhook as ControllerWebhook
from .input import Input


class Webhook(Input):
    webhook_id: str = "webhook"

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

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=event_type,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=node_type,
            node_id=self.id,
            o_connection=None,
            variables=self.room.all_variables | self.default_variables,
        )

    async def change_state_to_input(self, webhook: ControllerWebhook) -> None:
        """
        This function changes the state of the room to input.
        It also updates the menu for the room.
        It sends a node event to the room with the webhook data.

        Parameters
        ----------
        webhook : ControllerWebhook
            The webhook data.
        """
        await self.room.update_menu(node_id=self.id, state=RouteState.INPUT)

        if self.inactivity_options:
            self.log.debug(f"Webhook inactivity options: {self.inactivity_options}")
            self.inactivity_task(webhook)

        await self.send_node_event(
            o_connection=None,
            event_type=MenuflowNodeEvents.NodeEntry,
            node_type=Nodes.webhook,
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

        if evt.content.body.lower() != self.webhook_id:
            o_connection = await self.input_text(text=evt.content.body)

        if o_connection:
            self.log.debug(f"Deleting webhook from db: {self.room.room_id}")
            await Util.cancel_task(task_name=self.room.room_id)
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

        await self.send_node_event(
            o_connection=o_connection, event_type=MenuflowNodeEvents.NodeInputData
        )

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

        o_connection = await self.get_case_by_id(self.webhook_id)
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
                f"""
                Webhook filter {webhook.filter} matched for room {self.room.room_id} with event:
                {event}
                """
            )

            event_to_managed = event
            break

        return event_to_managed

    async def run(self, evt: dict | None) -> dict:
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
                    f"""Error decoding JSON for event {event_to_manage.id}.
                    Event: {event_to_manage.event}"""
                )
                return

            return

        if not isinstance(evt, MessageEvent) and self.room.route.state == RouteState.INPUT:
            o_connection = await self.management_webhook(evt=evt)

            if o_connection:
                await self.room.matrix_client.algorithm(room=self.room)

            return

        if self.room.route.state != RouteState.INPUT:
            await self.change_state_to_input(webhook)
            return

        if isinstance(evt, MessageEvent):
            await self.management_message(evt=evt, webhook=webhook)
            return

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
            self.log.debug(f"Room {self.room.room_id} does not have a route filter")
            return False

        if not webhook_filter == filter_db:
            self.log.debug(
                f"Webhook filter does not match the filter for room {self.room.room_id}"
            )
            self.log.debug(f"Webhook filter for room {self.room.room_id}: {webhook_filter}")
            self.log.debug(f"Filter from db in webhook node for {self.room.room_id}: {filter}")
            return False

        # Check if the room is waiting for a webhook event validating the filter
        jq_result: dict = Util.jq_compile(filter=webhook_filter, json_data=event_data)

        if jq_result.get("status") != 200:
            self.log.error(
                f"""Error parsing '{filter}' with jq on variable '{event_data}'.
                Error message: {jq_result.get("error")}, Status: {jq_result.get("status")}
                Room_id: {self.room.room_id}
                """
            )
            return False

        if not jq_result.get("result")[0]:
            self.log.debug(
                f"Webhook filter does not match the event data for room {self.room.room_id}"
            )
            self.log.debug(f"Webhook filter: {webhook_filter}")
            self.log.debug(f"Event data: {event_data}")
            return False

        return True

    @property
    def inactivity_options(self) -> dict[str, Any]:
        """
        This property returns the inactivity options for the webhook.
        """
        data: dict = self.content.get("inactivity_options", {})
        self.chat_timeout: int = data.get("chat_timeout", 0)

        return data

    def inactivity_task(self, webhook: ControllerWebhook):
        """It spawns a task to harass the client to enter information to input option

        Parameters
        ----------
        client : MatrixClient
            The MatrixClient object

        """
        self.chat_timeout = self.inactivity_options.get("chat_timeout", 0)

        if not self.chat_timeout or self.chat_timeout <= 0:
            self.log.debug(
                f"Chat timeout is not set in node webhook for room: {self.room.room_id}"
            )
            return

        if Util.get_tasks_by_name(task_name=self.room.room_id):
            self.log.debug(f"Task already exists for room: {self.room.room_id}")
            return

        self.log.debug(f"Inactivity loop starts in room: {self.room.room_id}")
        return asyncio.create_task(self.timeout_active_chats(webhook), name=self.room.room_id)

    def calculate_timeout(self, time_out_db: int) -> int:
        """
        This function calculates the timeout for the webhook.
        Parameters
        ----------
        time_out_db : int
            The timeout value from the database.
        Returns
        -------
        int
            The calculated timeout value. If the value is less than 0, it returns 0.
        """

        if not time_out_db or time_out_db <= 0:
            self.log.debug(f"Chat timeout is not set for room: {self.room.room_id}")
            return 0

        self.log.debug(f"Chat timeout is set for room: {self.room.room_id}")

        # Calculate the timeout
        time_out = int(time()) - time_out_db
        time_out = self.chat_timeout - abs(time_out)

        if time_out <= 0:
            return 0

        return time_out

    async def timeout_active_chats(self, webhook: ControllerWebhook):
        """It wait in time interval to cancel the webhook request and go to the next node

        Parameters
        ----------
        client : MatrixClient
            The Matrix client object.

        """
        time_out = self.calculate_timeout(
            time_out_db=webhook.subscription_time,
        )

        # wait the given time to start the task
        await asyncio.sleep(time_out)

        self.log.debug(f"Inactivity loop: {datetime.now()} -> {self.room.room_id}")

        o_connection = await self.get_case_by_id("timeout")
        await self.room.update_menu(node_id=o_connection, state=None)

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeInputTimeout,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_id=self.id,
            o_connection=o_connection,
            variables=self.room.all_variables | self.default_variables,
        )

        await self.room.matrix_client.algorithm(room=self.room)

        self.log.debug(f"INACTIVITY COMPLETED -> {self.room.room_id}")
        self.log.debug(f"Deleting webhook from db: {self.room.room_id}")
        await webhook.remove()

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
                f"""Error parsing '{self.variables[variable]}' with jq
                on variable '{variable}'. Set to default value ({default_value}).
                Error message: {jq_result.get("error")}, Status: {jq_result.get("status")}"""
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
