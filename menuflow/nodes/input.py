from __future__ import annotations

from typing import List

from attr import dataclass, ib
from jinja2 import Template

from mautrix.types import SerializableAttrs

from ..utils.primitive import OConnection
from .message import Message


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Input(Message):
    validation: str = ib(default=None, metadata={"json": "validation"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    @property
    def rule(self) -> Template:
        return Template(self.validation)

    @property
    def load_cases(self):

        cases_dict = {}

        for case in self.cases:
            cases_dict[case.id] = case.o_connection

        return cases_dict

    async def run(self, variables: dict) -> OConnection:
        """It takes a dictionary of variables, runs the rule,
        and returns the connection that matches the case

        Parameters
        ----------
        variables : dict
            dict

        Returns
        -------
            The OConnection object

        """

        self.log.debug(f"Running pipeline {self.id}")

        res = None

        try:
            res = self.rule.render(**variables)
            if res == "True":
                res = True

            if res == "False":
                res = False

        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            res = "except"

        self.log.debug(res)

        return self.get_case_by_id(res)

    def get_case_by_id(self, id: str) -> str:

        try:
            cases = self.load_cases
            return cases[id]
        except KeyError:
            self.log.debug(f"Case not found {id}")
