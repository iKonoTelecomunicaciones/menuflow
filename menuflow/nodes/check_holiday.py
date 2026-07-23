from datetime import datetime

import pytz

from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import CheckHoliday as CheckHolidayModel
from ..room import Room
from ..utils import Nodes, Util
from .switch import Switch


class CheckHoliday(Switch):
    def __init__(
        self, check_holiday_data: CheckHolidayModel, room: Room, default_variables: dict
    ) -> None:
        Switch.__init__(self, check_holiday_data, room=room, default_variables=default_variables)
        self.content = check_holiday_data
        self.util = Util(self.config)

    @property
    def timezone(self) -> str:
        return self.render_data(self.content.get("timezone", "America/Bogota"))

    @property
    def country(self) -> str:
        return self.render_data(self.content.get("country_code", str))

    @property
    def subregion(self) -> str:
        return self.render_data(self.content.get("subdivision_code", str))

    @property
    def validate_date(self) -> str:
        return self.render_data(self.content.get("validate_date"))

    async def validate_connection(self) -> None:
        time_zone = pytz.timezone(self.timezone)
        date_to_validate = None

        if _date := self.validate_date:
            formats = ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y")
            for fmt in formats:
                try:
                    date_to_validate = time_zone.localize(datetime.strptime(_date, fmt))
                    break
                except ValueError:
                    continue

            if date_to_validate is None:
                self.log.error(
                    f"[{self.room.room_id}] Invalid date format ({_date}). "
                    "Today's date will be used instead."
                )

        return (
            await self.get_case_by_id("True")
            if self.check_holidays(date_to_validate or datetime.now(time_zone))
            else await self.get_case_by_id("False")
        )

    async def run(self):
        """If the current month, day, weekday, and time are within the specified ranges,
        then update the menu to the "True" case. Otherwise, update the menu to the "False" case

        """
        self.log.debug(f"[{self.room.room_id}] Entering check_holiday node {self.id}")

        o_connection = await self.validate_connection()

        await self.room.update_menu(node_id=o_connection, state=None)

        await send_node_event(
            config=self.room.config,
            send_event=self.content.get("send_event"),
            event_type=MenuflowNodeEvents.NodeEntry,
            room_id=self.room.room_id,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.check_holiday,
            node_id=self.id,
            o_connection=o_connection,
            variables=None,
            conversation_uuid=self.room.conversation_uuid,
        )

    def check_holidays(self, date: datetime) -> bool:
        """
        If the current date is a holiday, return True.
        Otherwise, return False.
        Parameters
        ----------
        date : datetime
            The current date and time.
        Returns
        -------
            A boolean value.
        """

        return self.util.is_holiday(
            date=date, country_code=self.country, subdivision_code=self.subregion
        )
