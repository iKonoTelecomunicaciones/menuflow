from __future__ import annotations

from typing import Dict, List

from ..repository import Switch as SwitchModel
from .base import Base, convert_to_bool


class Switch(Base):
    def __init__(self, switch_node_data: SwitchModel) -> None:
        self.log = self.log.getChild(switch_node_data.get("id"))
        self.data: Dict = switch_node_data

    @property
    def validation(self) -> str:
        return self.render_data(data=self.data.get("validation"))

    @property
    def cases(self) -> List[Dict]:
        return self.render_data(self.data.get("cases"))

    async def load_cases(self) -> Dict[str, str]:
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

        for case in self.cases:
            cases_dict[convert_to_bool(case.get("id"))] = {
                "o_connection": case.get("o_connection"),
                "variables": case.get("variables"),
            }
        return cases_dict

    async def _run(self) -> str:
        """It takes a dictionary of variables, runs the rule,
        and returns the connection that matches the case

        Returns
        -------
            The str object

        """

        self.log.debug(f"Executing validation of input [{self.id}] for room [{self.room.room_id}]")

        result = None

        try:
            result = self.validation
        except Exception as e:
            self.log.warning(f"An exception has occurred in the pipeline [{self.id} ]:: {e}")
            result = "except"

        return await self.get_case_by_id(result)

    async def run(self) -> str:
        await self.room.update_menu(await self._run())

    async def get_case_by_id(self, id: str | int) -> str:
        try:
            cases = await self.load_cases()
            case_result: Dict = (
                cases[int(id)] if isinstance(id, str) and id.isdigit() else cases[id]
            )

            variables_recorded = []
            if case_result.get("variables") and self.room:
                for variable in case_result.get("variables", {}):
                    if variable in variables_recorded:
                        continue

                    await self.room.set_variable(
                        variable_id=variable,
                        value=self.render_data(case_result["variables"][variable]),
                    )
                    variables_recorded.append(variable)

            case_o_connection = case_result.get("o_connection")

            self.log.debug(
                f"The case [{case_o_connection}] has been obtained in the input node [{self.id}]"
            )
            return case_o_connection
        except KeyError:
            self.log.debug(f"Case [{id}] not found; the [default case] will be sought")
            return cases.get("default", {}).get("o_connection", "start")
