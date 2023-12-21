from typing import Dict, List

from ..db.route import RouteState
from ..repository import SetVars as SetVarsModel
from ..room import Room
from .base import Base


class SetVars(Base):
    def __init__(
        self, set_vars_node_data: SetVarsModel, room: Room, default_variables: Dict
    ) -> None:
        Base.__init__(self, room=room, default_variables=default_variables)
        self.log = self.log.getChild(set_vars_node_data.get("id"))
        self.content: Dict = set_vars_node_data

    @property
    def variables(self) -> SetVarsModel:
        return self.render_data(data=self.content.get("variables", ""))

    @property
    def o_connection(self) -> str:
        return self.render_data(self.content.get("o_connection", ""))

    async def run(self):
        """This function runs the set_var node."""
        self.log.debug(f"Room {self.room.room_id} enters set_var node {self.id}")
        if not self.variables:
            self.log.warning(
                f"The variables in {self.id} have not been set because they are empty"
            )
            return

        try:
            # Set variables
            set_vars: Dict = self.variables.get("set")
            if set_vars:
                await self.room.set_variables(variables=set_vars)

            # Unset variables
            unset_vars: List = self.variables.get("unset")
            if unset_vars:
                await self.room.del_variables(variables=unset_vars)
        except ValueError as e:
            self.log.warning(e)

        await self.room.update_menu(
            node_id=self.o_connection,
            state=RouteState.END if not self.o_connection else None,
        )
