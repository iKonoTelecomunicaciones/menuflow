from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from dataclass_wizard import JSONWizard


@dataclass
class Variable:
    id: str
    data: Union[int, str]


@dataclass
class Message:
    id: str
    text: str
    i_connection: str
    o_connection: str = None
    i_rule: Optional[str] = None
    i_rule_fail_message: Optional[str] = None
    timeout: Optional[int] = None
    active: Optional[bool] = None
    reset: Optional[bool] = None

    async def reset_menu(self):
        """The function waits for the defined time to know whether to reset the chat.
        If the user has reached the maximum waiting time, the chat is reset.

        """

        while self.active:
            # Waiting for the defined time to know whether to reset the chat
            await asyncio.sleep(self.timeout)
            if self.active and self.reset:
                # TODO reset MenuFlow
                self.log.debug(
                    f"The user has reached the maximum waiting time. Resetting the chat"
                )
                break


@dataclass
class Filter:
    id: str
    var_x: str
    var_y: Optional[str]
    operator: str
    o_connection: str
    else_o_connection: str

    def validate(self):
        """If the operator is equal to "==",
        then check if the variable x is equal to variable y.
        If it is, then return.
        If it's not,
        then go to the else_o_connection

        Returns
        -------
            The o_connection is being returned.
        """

        if self.operator == "==":
            if self.__equal(self.var_x, self.var_y):
                return

        if self.operator == "!=":
            if self.__not_equal(self.var_x, self.var_y):
                return

        if self.operator == ">":
            if self.__greater_than(self.var_x, self.var_y):
                return

        if self.operator == "<":
            if self.__less_than(self.var_x, self.var_y):
                return

        if self.operator == "empty":
            if self.__is_none(self.var_x):
                return

        if self.operator == "not_empty":
            if self.__not_is_none(self.var_x):
                return

        self.o_connection = self.else_o_connection

    def __equal(self, x: Any, y: Any) -> bool:
        return True if x == y else False

    def __not_equal(self, x: Any, y: Any) -> bool:
        return True if x != y else False

    def __greater_than(self, x: Any, y: Any) -> bool:
        return True if x > y else False

    def __less_than(self, x: Any, y: Any) -> bool:
        return True if x < y else False

    def __is_none(self, x: Any) -> bool:
        return bool(x is None)

    def __not_is_none(self, x: Any) -> bool:
        return bool(x is None)


@dataclass
class RandomOption:

    fk_random_selection: str
    text: str
    probability: int
    # Next action
    o_connection: str = ""


@dataclass
class RandomSelection:
    id: str
    # Previous action
    i_connection: str = ""
    random_options = List[RandomOption]


@dataclass
class MenuFlow(JSONWizard):
    id: str
    variables: List[Variable]
    filters: List[Filter]
    messages: List[Message]

    messages_by_id: Dict[str, Message] = field(default_factory=dict)

    @classmethod
    def _from_row(cls, data: Dict):
        return cls(**data)

    def get_message_by_id(self, msg_id: str) -> Message | None:
        """If the message is in the cache, return it. Otherwise, search the list of messages
        for the message with the given ID, and if it's found, add it to the cache and return it.

        The first thing we do is try to get the message from the cache. If it's not there,
        we'll get a KeyError exception, and we'll catch it and continue on

        Parameters
        ----------
        msg_id : str
            The ID of the message you want to get.

        Returns
        -------
            A message object

        """

        try:
            return self.messages_by_id[msg_id]
        except KeyError:
            pass

        for message in self.messages:
            if msg_id == message.i_connection:
                self.messages_by_id[msg_id] = message
                return message
