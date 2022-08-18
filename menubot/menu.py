from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from dataclass_wizard import JSONWizard
from jinja2 import Template
from mautrix.util.logging import TraceLogger

from .jinja_template import (DEFAULT, GREATER_THAN, IS_EQUAL, LESS_THAN,
                             NOT_IS_EQUAL, NUMBER)
from .primitive import ElseOConnection, IConnection, OConnection

I_RULES_TEMPLATES = {"NUMBER": NUMBER}

class Base:
    log: TraceLogger = logging.getLogger("maubot")

@dataclass
class Variable:
    id: str
    data: Union[int, str]


@dataclass
class Validation:
    var_x: str
    var_y: str
    operator: str
    v_rule: Any = None  # Template

    @property
    def load_variables(self):
        """It takes the operator and the two variables,
        and then it sets the rule to be used in the `evaluate` function
        """

        if self.operator == "GREATER_THAN":
            self.v_rule = GREATER_THAN
        elif self.operator == "IS_EQUAL":
            self.v_rule = IS_EQUAL
        elif self.operator == "IS_NUMBER":
            self.v_rule = IS_NUMBER
        elif self.operator == "LESS_THAN":
            self.v_rule = LESS_THAN
        elif self.operator == "NOT_IS_EQUAL":
            self.v_rule = NOT_IS_EQUAL

    def check(self, variables: Dict[str, Variable]) -> bool:
        """If the rule is a Python function, then it is called with the variables as arguments

        Returns
        -------
            The result of the rule being rendered with the variables.
        """

        _variables = {}

        if self.var_x.startswith("$"):
            try:
                _variables["var_x"] = variables[self.var_x]
            except KeyError:
                pass
        else:
            _variables["var_x"] = self.var_x

        if self.var_y.startswith("$"):
            try:
                _variables["var_y"] = variables[self.var_y]
            except KeyError:
                pass
        else:
            _variables["var_y"] = self.var_y

        self.load_variables
        if _variables:
            return self.v_rule.render(**_variables)


@dataclass
class Filter(JSONWizard):
    id: str
    validations: List[Validation] = field(default_factory=list)
    o_connection: OConnection = ""
    else_o_connection: ElseOConnection = ""

    def check(self, variables: Dict[str, Variable]) -> OConnection | ElseOConnection:
        """It checks if the validations are all the same.

        Returns
        -------
            The o_connection if all the validations are the same, else the else_o_connection.
        """

        resuls = [validation.check(variables) for validation in self.validations]
        return (
            self.o_connection if not (len(resuls) == len(set(resuls))) else self.else_o_connection
        )


@dataclass
class Message(Base):
    id: str
    text: str
    i_connection: IConnection = ""
    o_connection: OConnection = ""
    i_rule: Optional[str] = ""
    i_rule_fail_message: Optional[str] = ""
    timeout: Optional[int] = None
    reset: Optional[bool] = False
    variables: Dict[str, Any] = field(default_factory=dict)
    variable: Optional[str] = ""
    i_variable: Optional[Variable] = None

    @property
    def load_variables(self):
        """The function loads the variables from the input form into the variables dictionary"""
        try:
            self.variables["i_variable"] = self.i_variable.data
            if self.variable:
                self.variables[self.variable] = self.i_variable.data
        except KeyError:
            pass

        try:
            self.variables["i_rule_fail_message"] = self.i_rule_fail_message
        except KeyError:
            pass

    @property
    def check(self) -> str:
        """If the variables and i_rule are defined, then return the template for the i_rule with
        the variables

        Returns
        -------
            The template for the i_rule.
        """
        self.load_variables
        if self.variables and self.i_rule:
            return (
                (True, self.o_connection)
                if I_RULES_TEMPLATES[self.i_rule].render(**self.variables)
                else (False, self.i_rule_fail_message)
            )

    async def reset_menu(self):
        """The function waits for the defined time to know whether to reset the chat.
        If the user has reached the maximum waiting time, the chat is reset.
        """

        while self.active:
            # Waiting for the defined time to know whether to reset the chat
            await asyncio.sleep(self.timeout)
            if self.reset:
                # TODO reset MenuFlow
                self.log.debug(
                    f"The user has reached the maximum waiting time. Resetting the chat"
                )
                break


@dataclass
class MenuFlow(JSONWizard, Base):
    id: str
    variables: List[Variable]
    filters: List[Filter]
    messages: List[Message]

    message_by_id: Dict[str, Message] = field(default_factory=dict)
    variable_by_id: Dict[str, Variable] = field(default_factory=dict)
    filter_by_id: Dict[str, Filter] = field(default_factory=dict)

    @classmethod
    def _from_row(cls, data: Dict):
        """It takes a dictionary and returns an instance of the class"""
        return cls(**data)

    def get_variable_by_id(self, variable_id: str) -> Variable | None:
        """It returns the variable with the given id, or None if no such variable exists

        Parameters
        ----------
        variable_id : str
            The ID of the variable to get.

        Returns
        -------
            A variable object
        """

        try:
            return MenuFlow.variable_by_id[variable_id]
        except KeyError:
            pass

        for variable in self.variables:
            if variable_id == variable.id:
                self.variable_by_id[variable_id] = variable
                return variable

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
            return self.message_by_id[msg_id]
        except KeyError:
            pass

        for message in self.messages:

            if msg_id == message.id:
                self.message_by_id[msg_id] = message
                return message


    def get_filter_by_id(self, filter_id: str) -> Filter | None:

        try:
            return self.filter_by_id[filter_id]
        except KeyError:
            pass

        for filter in self.filters:
            if filter_id == filter.id:
                self.filter_by_id[filter_id] = filter
                return filter

    def check_filter(self, filter: Filter):
        self.log.debug(self.variable_by_id)
        return filter.check(self.variable_by_id)
