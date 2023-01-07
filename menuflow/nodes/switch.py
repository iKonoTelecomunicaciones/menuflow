from typing import Dict, List

from attr import dataclass, ib
from jinja2 import Template
from mautrix.types import SerializableAttrs

from ..jinja.jinja_template import jinja_env
from .node import Node


@dataclass
class Case(SerializableAttrs):
    id: str = ib(metadata={"json": "id"})
    variables: Dict = ib(metadata={"json": "variables"}, factory=dict)
    o_connection: str = ib(default=None, metadata={"json": "o_connection"})


@dataclass
class Switch(Node):
    """
    ## Switch

    A switch type node allows to validate the content of a jinja variable,
    and from the result to transit to another node.

    content:

    ```
    - id: switch-1
      type: switch
      validation: '{{ opt }}'
      cases:
      - id: 1
        o_connection: m1
      - id: 2
        o_connection: m2
      - id: default
        o_connection: m3
    ```
    """

    validation: str = ib(default=None, metadata={"json": "validation"})
    cases: List[Case] = ib(metadata={"json": "cases"}, factory=list)

    async def load_cases(self):
        """It loads the cases into a dictionary.

        Parameters
        ----------
        room : Room
            Room = None

        Returns
        -------
            A dictionary of cases.

        """

        cases_dict = {}

        variables_recorded = []

        for case in self.cases:

            cases_dict[str(case.id)] = case.o_connection
            if case.variables and self.room:
                for varible in case.variables.__dict__:

                    if varible in variables_recorded:
                        continue

                    await self.room.set_variable(
                        variable_id=varible,
                        value=self.render_data(case.variables[varible]),
                    )
                    variables_recorded.append(varible)

        return cases_dict

    async def run(self) -> str:
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

        self.log.debug(f"Executing validation of input [{self.id}] for room [{self.room.room_id}]")

        result = None

        try:
            result = self.render_data(self.validation)
            # TODO What would be the best way to handle this, taking jinja into account?
            # if res == "True":
            #     res = True

            # if res == "False":
            #     res = False

        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline [{self.id} ]:: {e}")
            result = "except"

        return await self.get_case_by_id(str(result))

    async def get_case_by_id(self, id: str) -> str:
        try:
            cases = await self.load_cases()
            case_result = cases[id]
            self.log.debug(
                f"The case [{case_result}] has been obtained in the input node [{self.id}]"
            )
            return case_result
        except KeyError:
            self.log.debug(f"Case not found [{id}] the default case will be sought")
            return cases["default"]
