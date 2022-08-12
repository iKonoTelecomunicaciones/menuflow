from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from dataclass_wizard import JSONWizard
from jinja2 import Template

from .jinja_template import (
    DEFAULT,
    GREATER_THAN,
    IS_EQUAL,
    LESS_THAN,
    NOT_IS_EQUAL,
    NUMBER,
)
from .primitive import ElseOConnection, IConnection, OConnection

I_RULES_TEMPLATES = {"NUMBER": NUMBER}


@dataclass
class Variable:
    id: str
    data: Union[int, str]


@dataclass
class Validation:
    o_connection: OConnection
    else_o_connection: ElseOConnection
    var_x: str
    var_y: str
    operator: str
    v_rule: Any = None  # Template

    @property
    def load_variables(self):
        """It takes the operator and the two variables,
        and then it sets the rule to be used in the `evaluate` function
        """
        var_x = MenuFlow.get_variable_by_id(self.var_x)
        var_y = MenuFlow.get_variable_by_id(self.var_y)
        self.variables[var_x.id] = var_x.data
        self.variables[var_y.id] = var_y.data

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
        else:
            self.v_rule = DEFAULT

    @property
    def check(self) -> str:
        """The function `check` is a method of the class `Rule` that returns a string

        Returns
        -------
            The rendered rule.

        """
        self.load_variables
        if self.variables:
            return self.i_rule.render(**self.variables)


@dataclass
class Filter(JSONWizard):
    id: str
    validations: List[Validation] = field(default_factory=list)


@dataclass
class Message:
    id: str
    text: str
    i_connection: IConnection = ""
    o_connection: OConnection = ""
    i_rule: Optional[str] = ""
    i_rule_fail_message: Optional[str] = ""
    timeout: Optional[int] = None
    reset: Optional[bool] = False
    variables: Dict[str, Any] = field(default_factory=dict)
    i_variable: Optional[Variable] = None

    @property
    def load_variables(self):
        try:
            self.variables["i_variable"] = self.i_variable.data
        except KeyError:
            pass

        try:
            self.variables["i_rule_fail_message"] = self.i_rule_fail_message
        except KeyError:
            pass

    @property
    def check(self) -> str:
        """The function `check` is a property that returns the string representation of the
        `i_rule` template, with the variables in the `variables` dictionary substituted for the
        template variables

        Returns
        -------
            The i_rule is being returned.

        """
        self.load_variables
        if self.variables and self.i_rule:
            return I_RULES_TEMPLATES[self.i_rule].render(**self.variables)

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
class MenuFlow(JSONWizard):
    id: str
    variables: List[Variable]
    filters: List[Filter]
    messages: List[Message]

    message_by_id: Dict[str, Message] = field(default_factory=dict)
    variable_by_id: Dict[str, Variable] = field(default_factory=dict)
    filters_by_id: Dict[str, Filter] = field(default_factory=dict)

    @classmethod
    def _from_row(cls, data: Dict):
        return cls(**data)

    @classmethod
    def get_variable_by_id(cls, variable_id: str) -> Variable | None:
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
            return cls.variable_by_id[variable_id]
        except KeyError:
            pass

        for variable in cls.variables:
            if variable_id == variable.id:
                cls.variable_by_id[variable_id] = variable
                return variable

    def get_message_by_id(cls, msg_id: str) -> Message | None:
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
            return cls.message_by_id[msg_id]
        except KeyError:
            pass

        for message in cls.messages:
            if msg_id == message.i_connection:
                cls.message_by_id[msg_id] = message
                return message
