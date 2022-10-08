from __future__ import annotations

from typing import Dict, List

from attr import dataclass, ib
from jinja2 import Template

from mautrix.types import SerializableAttrs

from ..user import User
from .message import Message


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Input(Message):
    validation: str = ib(default=None, metadata={"json": "validation"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    @property
    def rule(self) -> Template:
        return Template(self.validation)

    async def load_cases(self, user: User = None):

        cases_dict = {}

        for case in self.cases:
            cases_dict[str(case.id)] = case.o_connection
            if case.variables and user:
                for varible in case.variables.__dict__:
                    await user.set_variable(variable_id=varible, value=case.variables[varible])

        return cases_dict

    async def run(self, user: User) -> str:
        """It takes a dictionary of variables, runs the rule,
        and returns the connection that matches the case

        Parameters
        ----------
        variables : dict
            dict

        Returns
        -------
            The str object

        """

        self.log.debug(f"Running pipeline {self.id}")

        res = None

        try:
            res = self.rule.render(**user._variables)
            if res == "True":
                res = True

            if res == "False":
                res = False

        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            res = "except"

        self.log.debug(res)

        return await self.get_case_by_id(res, user=user)

    async def get_case_by_id(self, id: str, user: User = None) -> str:
        try:
            cases = await self.load_cases(user=user)
            return cases[id]
        except KeyError:
            self.log.debug(f"Case not found {id}")
            return cases["default"]
