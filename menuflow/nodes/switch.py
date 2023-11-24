from __future__ import annotations

from typing import Dict, List

from ..events import MenuflowNodeEvents
from ..events.event_generator import send_node_event
from ..repository import Switch as SwitchModel
from ..room import Room
from .base import Base, safe_data_convertion
from .types import Nodes


class Switch(Base):
    # Keeps track of the number of validation attempts made in a switch node by room.
    VALIDATION_ATTEMPTS_BY_ROOM: Dict[str, int] = {}

    def __init__(self, switch_node_data: SwitchModel, room: Room, default_variables: Dict) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(switch_node_data.get("id"))
        self.content: Dict = switch_node_data

    @property
    def validation(self) -> str:
        return self.render_data(data=self.content.get("validation"))

    @property
    def validation_attempts(self) -> int | None:
        return self.content.get("validation_attempts", None)

    @property
    def cases(self) -> List[Dict]:
        return self.content.get("cases")

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
            cases_dict[safe_data_convertion(case.get("id"))] = {
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

    async def run(self, generate_event: bool = True) -> str:
        o_connection = await self._run()
        await self.room.update_menu(o_connection)

        if generate_event:
            await send_node_event(
                config=self.room.config,
                send_event=self.content.get("send_event"),
                event_type=MenuflowNodeEvents.NodeEntry,
                room_id=self.room.room_id,
                sender=self.room.matrix_client.mxid,
                node_type=Nodes.switch,
                node_id=self.id,
                o_connection=o_connection,
                variables={**self.room._variables, **self.default_variables},
            )

        return o_connection

    async def get_case_by_id(self, id: str | int) -> str:
        id = safe_data_convertion(id)

        try:
            cases = await self.load_cases()
            case_result: Dict = cases[id]

            # Load variables defined in the case into the room
            await self.load_variables(case_result)

            case_o_connection = self.render_data(case_result.get("o_connection"))

            self.log.debug(
                f"The case [{case_o_connection}] has been obtained in the input node [{self.id}]"
            )

            if self.validation_attempts and self.room.room_id in self.VALIDATION_ATTEMPTS_BY_ROOM:
                del self.VALIDATION_ATTEMPTS_BY_ROOM[self.room.room_id]

            return case_o_connection
        except KeyError:
            default_case, o_connection = await self.manage_case_exceptions()
            self.log.debug(f"Case [{id}] not found; the [{default_case} case] will be sought")
            return self.render_data(o_connection)

    async def load_variables(self, case: Dict) -> None:
        """This function loads variables defined in switch cases into the room.

        Parameters
        ----------
        case : Dict
            `case` is the selected switch case.

        """
        variables_recorded = []
        if case.get("variables") and self.room:
            for variable in case.get("variables", {}):
                if variable in variables_recorded:
                    continue

                await self.room.set_variable(
                    variable_id=variable,
                    value=self.render_data(case["variables"][variable]),
                )
                variables_recorded.append(variable)

    async def manage_case_exceptions(self) -> tuple[str, str]:
        """
        This function handles exceptions when getting cases in the switch node,
        if the selected case can not be found it provides a default case.

        Returns
        -------
            A tuple containing two strings:
            the first string is the name of the case being used
            (either "attempt_exceeded" or "default"),
            and the second string is the value of the "o_connection" key in the
            default case dictionary (or "start" if the key is not present).

        """
        cases = await self.load_cases()

        room_validation_attempts = self.VALIDATION_ATTEMPTS_BY_ROOM.get(self.room.room_id, 1)
        if self.validation_attempts and room_validation_attempts >= self.validation_attempts:
            if self.room.room_id in self.VALIDATION_ATTEMPTS_BY_ROOM:
                del self.VALIDATION_ATTEMPTS_BY_ROOM[self.room.room_id]
            case_to_be_used = "attempt_exceeded"
        else:
            case_to_be_used = "default"

        if self.validation_attempts and case_to_be_used == "default":
            self.log.critical(
                f"Validation Attempts {room_validation_attempts} "
                f"of {self.validation_attempts} for room {self.room.room_id}"
            )
            self.VALIDATION_ATTEMPTS_BY_ROOM[self.room.room_id] = room_validation_attempts + 1

        # Getting the default case
        default_case = cases.get(case_to_be_used, {})

        # Load variables defined in the case into the room
        await self.load_variables(default_case)

        return case_to_be_used, default_case.get("o_connection", "start")
