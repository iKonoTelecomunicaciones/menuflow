"""This module contains the HandleInactivity class for handling inactivity options in a room."""

import asyncio
from datetime import datetime
from logging import getLogger

from mautrix.util.logging import TraceLogger

from .room import Room

log: TraceLogger = getLogger("menuflow.handle_inactivity")


class InactivityHandler:
    def __init__(self, room: Room, inactivity: dict):
        """It initializes the InactivityHandler class."""
        self.room = room
        self.set_inactivity_options(inactivity)

    async def update_inactivity_db(self):
        """It update node vars with the inactivity options."""
        self.room.set_node_var(inactivity=self.inactivity_db)
        await self.room.route.update_node_vars()

    def set_inactivity_options(self, inactivity: dict):
        """It sets the inactivity options.

        Parameters
        ----------
        inactivity : dict
            The inactivity options.
        """
        log.info(f"Inactivity loop starts in room: {self.room.room_id}")
        self.inactivity_db = self.room.route._node_vars.setdefault("inactivity", {})
        self.inactivity_db.setdefault("attempt", 0)
        self.inactivity_db.setdefault("start_ttl", 0)
        self.inactivity_db.setdefault("attempt_ttl", 0)

        self.chat_timeout = inactivity.get("chat_timeout", 0) or 0
        self.warning_message = inactivity.get("warning_message", "")
        self.time_between_attempts = inactivity.get("time_between_attempts", 0) or 0
        self.attempts = inactivity.get("attempts", 0) or 0

    def valid_attempt(self) -> bool:
        """Checks if the current attempt is valid.

        - The validation includes the last recorded attempt.
        - If the system restarts while waiting for the last attempt
        and there is still pending time, the attempt must be considered valid.

        Returns
        -------
        bool
            Returns True if the attempt is valid, otherwise False.
        """
        if (
            self.inactivity_db["attempt"] == self.attempts
            and self.inactivity_db.get("attempt_ttl") - datetime.now().timestamp() > 0
        ):
            return True

        return self.inactivity_db["attempt"] < self.attempts

    async def start(self):
        """It spawns a task to harass the client to enter information to input option."""

        if self.inactivity_db["attempt"] == 0:

            start_time = datetime.now().timestamp()
            if self.inactivity_db.get("start_ttl") == 0:
                self.inactivity_db["start_ttl"] = start_time + self.chat_timeout
                await self.update_inactivity_db()

            start_sleep = self.inactivity_db["start_ttl"] - start_time
            log.info(
                f"Start chat timeout, sleeping {start_sleep} seconds for room {self.room.room_id}"
            )

            if start_sleep > 0:
                await asyncio.sleep(start_sleep)

        while self.valid_attempt():

            attempt_time = datetime.now().timestamp()
            if self.inactivity_db.get("attempt_ttl") - attempt_time < 0:
                self.inactivity_db["attempt_ttl"] = attempt_time + self.time_between_attempts
                self.inactivity_db["attempt"] += 1
                await self.update_inactivity_db()

                if self.warning_message:
                    await self.room.matrix_client.send_text(
                        room_id=self.room.room_id, text=self.warning_message
                    )

            attempt_sleep = self.inactivity_db["attempt_ttl"] - attempt_time
            log.info(
                f"Inactivity Attempts {self.inactivity_db['attempt']} of "
                f"{self.attempts} sleeping {attempt_sleep} seconds for room {self.room.room_id}"
            )

            if attempt_sleep > 0:
                await asyncio.sleep(attempt_sleep)
