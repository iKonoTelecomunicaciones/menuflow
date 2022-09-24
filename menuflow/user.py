from __future__ import annotations

from typing import Any, Dict, cast
import json

from mautrix.types import UserID

from . import menu as m, nodes as n
from .db.user import User as DBUser


class User(DBUser):

    by_user_id: Dict[UserID, "User"] = {}

    menu: m.Menu

    def __init__(
        self,
        user_id: UserID,
        context: str,
        state: str = None,
        id: int = None,
        variables: str = "{}",
    ) -> None:
        self._variables = json.loads(variables)
        super().__init__(
            id=id, user_id=user_id, context=context, state=state, variables=f"{variables}"
        )

    def _add_to_cache(self) -> None:
        if self.user_id:
            self.by_user_id[self.user_id] = self

    # @property
    # def phone(self) -> str | None:
    #     user_match = match("^@(?P<user_prefix>.+)_(?P<number>[0-9]{8,}):.+$", self.user_id)
    #     if user_match:
    #         return user_match.group("number")

    @property
    def node(self) -> n.Node | None:
        return self.menu.node(context=self.context)

    @classmethod
    async def get_by_user_id(cls, user_id: UserID, create: bool = True) -> "User" | None:
        """It gets a user from the database, or creates one if it doesn't exist

        Parameters
        ----------
        user_id : UserID
            The user's ID.
        create : bool, optional
            If True, the user will be created if it doesn't exist.

        Returns
        -------
            The user object

        """
        try:
            return cls.by_user_id[user_id]
        except KeyError:
            pass

        user = cast(cls, await super().get_by_user_id(user_id))

        if user is not None:
            user._add_to_cache()
            return user

        if create:
            user = cls(user_id=user_id, context="m1")

            await user.insert()
            user = cast(cls, await super().get_by_user_id(user_id))
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

    async def update_menu(self, context: str, state: str = None):
        """Updates the menu's context and state, and then updates the menu's content

        Parameters
        ----------
        context : str
            The context of the menu. This is used to determine which menu to display.
        state : str
            The state of the menu. This is used to determine which menu to display.

        """
        self.context = context
        self.state = state
        await self.update()
        self._add_to_cache()
