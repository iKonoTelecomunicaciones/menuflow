from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from attr import dataclass, ib
from mautrix.types import SerializableAttrs, UserID
from mautrix.util.logging import TraceLogger
from nats.js.client import JetStreamContext

from ..config import Config
from ..db.event_storage import sqlite_db
from ..utils.util import Util
from .event_types import MenuflowEventTypes, MenuflowNodeEvents
from .nats_publisher import NatsPublisher

log: TraceLogger = logging.getLogger("report.event")


@dataclass
class BaseEvent(SerializableAttrs):
    event_type: MenuflowEventTypes = ib(default=None)
    event: MenuflowNodeEvents = ib(default=None)
    timestamp: float = ib(factory=float)
    sender: UserID = ib(factory=UserID)

    async def send(self, config: Config):
        if config["nats.enabled"]:
            try:
                await self.send_to_nats()
            except Exception as e:
                log.exception(f"Error sending event to NATS: {e}")

        if config["events.write_to_file"]:
            self.write_to_file()

    def write_to_file(self):
        with open("/data/room_events.txt", "a") as file:
            file.write(f"{json.dumps(self.serialize())}\n\n")

    async def publish(
        self, config: Config, jetstream: JetStreamContext, event: Optional[str] = None
    ):
        event = event or json.dumps(self.serialize()).encode()
        cep_subject = f"{config['nats.subject']}_cep"
        mntr_subject = f"{config['nats.subject']}_mntr"

        await jetstream.publish(
            subject=f"{cep_subject}.{self.event_type}",
            payload=event,
        )
        await jetstream.publish(
            subject=f"{mntr_subject}.{self.event_type}",
            payload=event,
        )

    async def publish_from_storage(self, config: Config, jetstream: JetStreamContext):
        events = sqlite_db.get_events()
        for event in events:
            try:
                event_parsed = dict(event)
                await self.publish(
                    config, jetstream, event=str(event_parsed.get("event")).encode()
                )

                if config["events.sqlite_action"] == "all":
                    sqlite_db.update_event(event_parsed.get("id"), True)
                else:
                    sqlite_db.delete_event(event_parsed.get("id"))
            except Exception as e:
                log.error(f"Error publishing event to NATS: {e}")
                break

    async def send_to_nats(self):
        nats, jetstream = await NatsPublisher.get_connection()

        if not nats or not nats.is_connected or sqlite_db.get_events():
            log.error("NATS is not connected, saving event to sqlite")
            sqlite_db.insert_event(json.dumps(self.serialize()))
            if nats and nats.is_connected and not Util.get_tasks_by_name("publish_to_storage"):
                log.error("Creating task to publish to storage")
                asyncio.create_task(
                    self.publish_from_storage(NatsPublisher.config, jetstream),
                    name="publish_to_storage",
                )
        else:
            try:
                await self.publish(NatsPublisher.config, jetstream)
            except Exception as e:
                log.critical(f"Error publishing event to NATS: {e}, saving event to sqlite")
                sqlite_db.insert_event(json.dumps(self.serialize()))
            else:
                if NatsPublisher.config["events.sqlite_action"] == "all":
                    sqlite_db.insert_event(json.dumps(self.serialize()), True)
