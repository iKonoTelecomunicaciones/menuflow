from __future__ import annotations

import json
from logging import getLogger
from re import match
from typing import Any, Dict, cast

from mautrix.types import UserID
from mautrix.util.logging import TraceLogger

from .config import Config
from .db.user import User as DBUser


class User(DBUser):

    by_mxid: Dict[UserID, "User"] = {}

    config: Config
    log: TraceLogger = getLogger("menuflow.user")

    def __init__(
        self,
        mxid: UserID,
        node_id: str,
        state: str = None,
        id: int = None,
        variables: str = "{}",
    ) -> None:
        self._variables: Dict = json.loads(variables)
        super().__init__(id=id, mxid=mxid, node_id=node_id, state=state, variables=f"{variables}")
        self.log = self.log.getChild(self.mxid)

    def _add_to_cache(self) -> None:
        if self.mxid:
            self.by_mxid[self.mxid] = self

    @property
    def phone(self) -> str | None:
        user_match = match(self.config["utils.user_phone_regex"], self.mxid)
        if user_match:
            return user_match.group("number")

    @classmethod
    async def get_by_mxid(cls, mxid: UserID, create: bool = True) -> "User" | None:
        """It gets a user from the database, or creates one if it doesn't exist

        Parameters
        ----------
        mxid : UserID
            The user's ID.
        create : bool, optional
            If True, the user will be created if it doesn't exist.

        Returns
        -------
            The user object

        """
        try:
            return cls.by_mxid[mxid]
        except KeyError:
            pass

        user = cast(cls, await super().get_by_mxid(mxid))

        if user is not None:
            user._add_to_cache()
            return user

        if create:
            user = cls(mxid=mxid, node_id="start")

            await user.insert()
            user = cast(cls, await super().get_by_mxid(mxid))
            user._add_to_cache()
            return user

    async def get_varibale(self, variable_id: str) -> Any | None:
        """This function returns the value of a variable with the given ID

        Parameters
        ----------
        variable_id : str
            The id of the variable you want to get.

        Returns
        -------
            The value of the variable with the given id.

        """
        return self._variables.get(variable_id)

    async def set_variable(self, variable_id: str, value: Any):
        self._variables[variable_id] = value
        self.variables = json.dumps(self._variables)
        self.log.debug(f"Saving variable {variable_id} to user {self.mxid} :: content {value}")
        await self.update()

    async def set_variables(self, variables: Dict):
        """It takes a dictionary of variable IDs and values, and sets the variables to the values

        Parameters
        ----------
        variables : Dict
            A dictionary of variable names and values.

        """
        for variable in variables:
            await self.set_variable(variable_id=variable, value=variables[variable])

    async def update_menu(self, node_id: str, state: str = None):
        """Updates the menu's node_id and state, and then updates the menu's content

        Parameters
        ----------
        node_id : str
            The node_id of the menu. This is used to determine which menu to display.
        state : str
            The state of the menu. This is used to determine which menu to display.

        """
        self.log.debug(
            f"The [user: {self.mxid}] will update his [node: {self.node_id}] to [{node_id}] "
            f"and his [state: {self.state}] to [{state}]"
        )
        self.node_id = node_id
        self.state = state
        await self.update()
        self._add_to_cache()
