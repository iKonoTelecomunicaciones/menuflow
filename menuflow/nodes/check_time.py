from datetime import datetime
from typing import Any, Dict, List

import pytz

from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import CheckTime as CheckTimeModel
from ..room import Room
from ..utils import Util
from .switch import Switch
from .types import Nodes


class CheckTime(Switch):
    def __init__(
        self, check_time_node_data: CheckTimeModel, room: Room, default_variables: Dict
    ) -> None:
        Switch.__init__(self, check_time_node_data, room=room, default_variables=default_variables)
        self.content = check_time_node_data

    @property
    def time_ranges(self) -> List[str]:
        return self.render_data(self.content.get("time_ranges", []))

    @property
    def days_of_week(self) -> List[str]:
        return self.render_data(self.content.get("days_of_week", []))

    @property
    def days_of_month(self) -> List[str]:
        return self.render_data(self.content.get("days_of_month", []))

    @property
    def months(self) -> List[str]:
        return self.render_data(self.content.get("months", []))

    @property
    def timezone(self) -> str:
        return self.render_data(self.content.get("timezone", str))

    async def run(self):
        """If the current month, day, weekday, and time are within the specified ranges,
        then update the menu to the "True" case. Otherwise, update the menu to the "False" case

        """

        time_zone = pytz.timezone(self.timezone)
        now = datetime.now(time_zone)
        week_day: str = now.strftime("%a").lower()
        day: int = now.day
        month: int = now.month

        o_connection = (
            await self.get_case_by_id("True")
            if self.check_month(month)
            and self.check_month_days(day)
            and self.check_week_day(week_day)
            and self.check_hours(now.time())
            else await self.get_case_by_id("False")
        )

        await self.room.update_menu(node_id=o_connection, state=None)

        send_node_event(
            event_type=MenuflowNodeEvents.NodeEntry,
            sender=self.room.matrix_client.mxid,
            node_type=Nodes.check_time,
            node_id=self.id,
            o_connection=o_connection,
            variables={**self.room._variables, **self.default_variables},
        )

    def check_month(self, month: int) -> bool:
        """If the month are set to "*" (all months), then return True.
        Otherwise, check if the current month is within the range of months

        Parameters
        ----------
        month
            The month of the year, as a number from 1 to 12.

        Returns
        -------
            A boolean value.

        """

        if self.months[0] == "*":
            return True

        for range_months in self.months:
            month_start, month_end = range_months.split("-")
            if Util.is_within_range(
                month, Util.months.get(month_start), Util.months.get(month_end)
            ):
                return True

        return False

    def check_week_day(self, week_day: str) -> bool:
        """If the days of week are set to "*" (all days), then return True.
        Otherwise, check if the current day is within the range of the days of week

        Parameters
        ----------
        week_day
            The day of the week to check.

        Returns
        -------
            A boolean value.

        """

        if self.days_of_week[0] == "*":
            return True

        for week_days_range in self.days_of_week:
            week_day_start, week_day_end = week_days_range.split("-")
            if Util.is_within_range(
                Util.week_days.get(week_day),
                Util.week_days.get(week_day_start),
                Util.week_days.get(week_day_end),
            ):
                return True

        return False

    def check_month_days(self, day: int) -> bool:
        """If the days of the month are set to "*", then the day is valid.
        Otherwise, check if the day is within any of the ranges specified

        Parameters
        ----------
        day
            The day of the month to check.

        Returns
        -------
            A boolean value.

        """

        if self.days_of_month[0] == "*":
            return True

        for days_range in self.days_of_month:
            day_start, day_end = map(int, days_range.split("-"))
            if Util.is_within_range(day, day_start, day_end):
                return True

        return False

    def check_hours(self, current_time: Any) -> bool:
        """If the time range is "*", then return True.
        Otherwise, for each time range, split the time range into a start and end time,
        convert the start and end times to datetime objects,
        and if the current time is between the start and end times, return True.
        Otherwise, return False

        Parameters
        ----------
        current_time : Any
            The current time of the day.

        Returns
        -------
            A boolean value.

        """

        if self.time_ranges[0] == "*":
            return True

        for time_range in self.time_ranges:
            time_start, time_end = time_range.split("-")
            start_hour = datetime.strptime(time_start, "%H:%M").time()
            end_hour = datetime.strptime(time_end, "%H:%M").time()

            if start_hour < current_time < end_hour:
                return True

        return False
