from __future__ import annotations

import asyncio
import json
import logging

from attr import dataclass, ib
from mautrix.types import SerializableAttrs, UserID
from mautrix.util.logging import TraceLogger
from nats.js.client import JetStreamContext

from ..config import Config
from .event_types import MenuflowEventTypes, MenuflowNodeEvents
from .nats_publisher import NatsPublisher

log: TraceLogger = logging.getLogger("report.event")


@dataclass
class BaseEvent(SerializableAttrs):
    event_type: MenuflowEventTypes = ib(default=None)
    event: MenuflowNodeEvents = ib(default=None)
    timestamp: float = ib(factory=float)
    sender: UserID = ib(factory=UserID)

    def send(self, config: Config):
        log.error(f"Sending event {self.serialize()}")
        asyncio.create_task(self.send_to_nats())

        if config["events.write_to_file"]:
            self.write_to_file()

    def write_to_file(self):
        file = open("/data/room_events.txt", "a")
        file.write(f"{json.dumps(self.serialize())}\n\n")
        file.close()

    async def send_to_nats(self):
        jetstream: JetStreamContext = None
        _, jetstream = await NatsPublisher.get_connection()
        if jetstream:
            try:
                subject = NatsPublisher.config["nats.subject"]
                await jetstream.publish(
                    subject=f"{subject}.{self.event_type}",
                    payload=json.dumps(self.serialize()).encode(),
                )
            except Exception as e:
                log.error(f"Error publishing event to NATS: {e}")
