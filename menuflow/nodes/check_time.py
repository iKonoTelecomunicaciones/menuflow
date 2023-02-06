from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pytz
from attr import dataclass, ib

from ..utils.util import Util
from .switch import Case, Switch


@dataclass
class CheckTime(Switch):
    """
    ##CheckTime

    If the current time matches the specified time, it branches to the case `True`.
    Each of the elements can be specified as '*' (forever) or as a range.
    If the current time does not match the specified time the output will be set using case `False`.

    - id: "check_time_node"
    type: check_time
    timezone: "America/Bogota"
    time_ranges:
        - "08:00-12:00"
        - "13:00-18:00"
    days_of_week:
        - "mon-fri"
    days_of_month:
        - "8-12"
        - "6-6"
    months:
        - "*"
    cases:
        - id: "True"
        o_connection: "message_1"
        - id: "False"
        o_connection: "message_2"
    """

    time_ranges: List[str] = ib(metadata={"json": "time_ranges"}, factory=list)
    days_of_week: List[str] = ib(metadata={"json": "days_of_week"}, factory=str)
    days_of_month: List[str] = ib(metadata={"json": "days_of_month"}, factory=str)
    months: List[str] = ib(metadata={"json": "months"}, factory=str)
    timezone: str = ib(metadata={"json": "timezone"}, factory=str)
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    async def check_time(self):
        """If the current month, day, weekday, and time are within the specified ranges,
        then update the menu to the "True" case. Otherwise, update the menu to the "False" case

        """
        o_connection: str = None
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

    def check_month(self, month):
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

        months: Dict[str, int] = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

        if self.months[0] == "*":
            return True

        for range_month in self.months:
            month_start, month_end = range_month.split("-")
            if Util.is_within_range(month, months.get(month_start), months.get(month_end)):
                return True

        return False

    def check_week_day(self, week_day):
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

        days: Dict[str, int] = {
            "mon": 1,
            "tue": 2,
            "wed": 3,
            "thu": 4,
            "fri": 5,
            "sat": 6,
            "san": 7,
        }

        if self.days_of_week[0] == "*":
            return True

        for week_days_range in self.days_of_week:
            week_day_start, week_day_end = week_days_range.split("-")
            if Util.is_within_range(
                days.get(week_day), days.get(week_day_start), days.get(week_day_end)
            ):
                return True

        return False

    def check_month_days(self, day):
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

    def check_hours(self, current_time: Any):
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

            if current_time > start_hour and current_time < end_hour:
                return True

        return False
