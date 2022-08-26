from __future__ import annotations

import re
from abc import abstractmethod
from typing import Dict, List

from mautrix.types import UserID

from menu import Variable


class User:
    user_id: UserID
    variables: List[Variable] = None
    context: str
    state: str

    variable_by_id: Dict = {}
    by_phone: Dict = {}
    by_user_id: Dict = {}

    @property
    def phone(self):
        user_match = re.match(REGEX, self.user_id)
        if user_match:
            return user_match.group("number")

    @property
    def add_to_cache(self):

        self.by_user_id[self.user_id] = self

        if self.phone:
            self.by_phone[self.phone] = self

    def __init__(self, user_id, variables, context, state) -> None:
        self.user_id = user_id
        self.variables = variables
        self.context = context
        self.state = state

    @abstractmethod
    def get_by_phone(cls, phone) -> "User" | None:
        try:
            return cls.by_phone[phone]
        except KeyError:
            pass




    def get_varibale(self, variable_id: str) -> Variable:

        try:
            return self.variable_by_id[variable_id]
        except KeyError:
            pass

        for variable in self.variables:
            if variable_id == variable.id:
                self.set_variable(variable=variable)
                return variable

    def set_variable(self, variable: Variable):
        if not variable:
            return
        self.variable_by_id[variable.id] = variable
        self.variables.append(variable)

    def update_menu(self, context: str):

        self.context = context

        if context.startswith("#pipeline"):
            self.state = "VALIDATE_PIPE"

        if context.startswith("#message"):
            self.state = "SHOW_MESSAGE"
