from __future__ import annotations

from typing import List

from attr import dataclass, ib
from jinja2 import Template

from mautrix.types import SerializableAttrs

from .user import User
from .utils.base_logger import BaseLogger


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Pipeline(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    validation: str = ib(metadata={"json": "validation"})
    variable: str = ib(default=None, metadata={"json": "variable"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    @property
    def template(self) -> Template:
        return Template(self.validation)

    async def run(self, user: User):
        """It takes a user object, runs the pipeline,
        and updates the user's menu based on the result

        Parameters
        ----------
        user : User
            User

        """

        self.log.debug(f"Running pipeline {self.id}")

        case_res = None

        self.log.debug(f"#### {user.variable_by_id}")

        try:
            res = self.template.render(**user.variable_by_id)
            if res == "True":
                res = True

            if res == "False":
                res = False

            case_res = Case(id=res)
        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline {self.id} :: {e}")
            case_res = Case(id="except")

        for case in self.cases:
            if case_res.id == case.id:
                await user.update_menu(context=case.o_connection)
                self.log.debug(f"##### {user}")
                break
