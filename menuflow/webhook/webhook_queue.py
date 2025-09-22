import asyncio
import logging
from time import time

from mautrix.util.logging import TraceLogger

from menuflow.config import Config
from menuflow.db.webhook_queue import WebhookQueue as WebhookQueueDB


class WebhookQueue(WebhookQueueDB):
    log: TraceLogger = logging.getLogger("menuflow.handler_webhook")
    events_queue: dict = {}
    config: Config | None = None
    tasks: dict[int, asyncio.Task] = {}

    def __init__(
        self,
        config: Config | None = None,
        id: int = None,
        event: str = None,
        ending_time: int = None,
        creation_time: int = None,
    ) -> None:
        event = event or "{}"
        ending_time = ending_time or 0
        creation_time = creation_time or int(time() * 1000)
        self.config = self.config or config

        self.log = self.log.getChild("WebhookQueue")
        super().__init__(id=id, event=event, ending_time=ending_time, creation_time=creation_time)
        self.log.debug("WebhookQueue initialized")

    def calculate_time_finished(self, event: WebhookQueueDB) -> bool:
        """
        This function calculates if a webhook event finished it's time waiting
        Parameters
        ----------
        event : WebhookQueue
            The webhook event from the database.
        Returns
        -------
        bool
            True if the event has finished, False otherwise.
        """
        self.log.debug(f"Calculating time finished for event {event.id}")

        # Calculate the time finished for the event
        time_finished = int(time() * 1000) - event.creation_time
        time_finished = (event.ending_time * 1000) - abs(time_finished)

        if time_finished <= 0:
            return True

        return False

    async def _validate_event_expiration(self, event: WebhookQueueDB) -> bool:
        """
        This function validates if the event has expired based on its ending time and removes it
        from the database if it has.

        Parameters
        ----------
        event : WebhookQueue
            The webhook event to validate.

        Returns
        -------
        bool
            True if the event has expired, False otherwise.
        """
        if self.calculate_time_finished(event):
            self.log.debug(f"Event {event.id} has finished, removing from queue")
            await self.remove_event_from_queue(id=event.id)
            self.log.debug(f"Event {event.id} removed from queue")
            return True

        return False

    async def get_events_from_db(self) -> list[WebhookQueueDB] | None:
        """
        This function retrieves events from the database and returns them as a list of
        WebhookQueue objects.

        Returns
        -------
        list[WebhookQueue] | None
            A list of WebhookQueue objects if events are found, otherwise None.
        """
        self.log.debug("Retrieving events from the database")
        events = await self.get_all_data()

        return events if events else None

    async def save_events_to_queue(self) -> None:
        """
        This function retrieves events from the database and adds them to the queue.
        """
        events = await self.get_events_from_db()

        if not events:
            self.log.debug("No events found in the database")
            return

        for event in events:
            if await self._validate_event_expiration(event):
                self.log.debug(f"Event {event.id} has expired, ignoring...")
                continue

            self.log.debug(f"Adding event {event.id} to queue")
            await self.add_event_to_queue(event=event.event, event_id=event.id)

    async def timed_task(self, event_id: int, event: dict, delay: int):
        """
        Function to simulate a timed task that waits for a specified delay before cleaning up.

        Parameters
        ----------
        event_id: int
            Unique identifier for the event.
        event: dict
            Event data associated with the task.
        delay: int
            Time in seconds for which the task will wait before cleaning up.
        """
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self.log.debug(f"[{time():.2f}] Task '{event_id}' cancelled.")
            return

        # This part will be executed whether the task finishes normally or is cancelled
        if event_id in self.events_queue:
            del self.events_queue[event_id]
            self.log.debug(
                f"[{time():.2f}] Task '{event_id}' completed and data removed from dictionary."
            )

        if event_id in self.tasks:
            del self.tasks[event_id]
            self.log.debug(f"[{time():.2f}] Task '{event_id}' removed from tasks dictionary.")

        event = await self.get_event_by_id(id=event_id)
        if event:
            self.log.debug(f"[{time():.2f}] Removing event {event.id} from database")
            await event.delete()

    async def get_event_id(self, event: dict) -> int | None:
        """
        This function gets the event ID from the database or creates a new one if it doesn't exist.

        Parameters
        ----------
        event : dict
            The event data to get the ID for.

        Returns
        -------
        int | None
            The ID of the event.
        """
        event_db = await self.get_event(event=event)

        if not event_db:
            self.log.debug(f"Event {event} not found in database, creating a new one")

            time_to_live = self.config["menuflow.webhook_queue.time_to_live"]

            # Save the event to the database
            self.event = event
            self.ending_time = time_to_live
            event_id = await self.insert()
            self.log.debug(f"Event {event} created with ID {event_id}")

            return event_id

        self.log.debug(f"Event {event} found in database with ID {event_db.id}")
        if await self._validate_event_expiration(event_db):
            self.log.debug(f"Event {event_db.id} has expired")
            return None

        return event_db.id

    async def add_event_to_queue(self, event: dict, event_id: int | None) -> None:
        """
        This function adds the event to the queue for the specified room ID.

        Parameters
        ----------
        id : str
            The ID of the event to add to the queue.
        event : dict
            The event data to add to the queue.
        """
        time_to_live = self.config["menuflow.webhook_queue.time_to_live"]

        if event_id is None:
            self.log.debug("Cannot add event to queue, the event ID is None")
            return

        # Create a task to handle the event after the time to live
        task_id = asyncio.create_task(self.timed_task(event_id, event, time_to_live))
        self.tasks[event_id] = task_id
        self.events_queue[event_id] = event
        self.log.debug(f"Webhook event saved to queue with ID {event_id}")

    async def remove_event_from_queue(self, id: int) -> None:
        """
        This function removes the event from the queue for the specified room ID.

        Parameters
        ----------
        id : str
            The ID of the event to remove from the queue.
        """
        try:
            del self.events_queue[id]
        except KeyError:
            self.log.debug(f"Event with ID {id} not found in queue, nothing to remove")

        try:
            self.log.debug(f"Cancelling task for event ID {id}")
            self.tasks[id].cancel()
            del self.tasks[id]
        except KeyError:
            self.log.debug(f"Task for event ID {id} not found, nothing to cancel")

        # Remove the event from the database
        event = await self.get_event_by_id(id)
        if event:
            self.log.debug(f"Removing event {event.id} from database")
            await event.delete()
