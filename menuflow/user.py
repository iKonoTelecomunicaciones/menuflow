from __future__ import annotations

from typing import Any, Dict, cast

from mautrix.types import UserID
from menuflow.menu import Menu

from .db.user import User as DBUser
from .nodes import HTTPRequest, Input, Message
from .variable import Variable


class User(DBUser):

    by_user_id: Dict[UserID, "User"] = {}
    variables_data: Dict[str, Any] = {}

    variables: Dict[str, Variable] = {}

    menu: Menu

    def __init__(self, user_id: UserID, context: str, state: str = None, id: int = None) -> None:
        super().__init__(id=id, user_id=user_id, context=context, state=state)

    def _add_to_cache(self) -> None:
        if self.user_id:
            self.by_user_id[self.user_id] = self

    async def load_variables(self):
        for variable in await Variable.all_variables_by_fk_user(self.id):
            self.variables_data[variable.variable_id] = variable.value
            self.variables[variable.variable_id] = variable

    # @property
    # def phone(self) -> str | None:
    #     user_match = match("^@(?P<user_prefix>.+)_(?P<number>[0-9]{8,}):.+$", self.user_id)
    #     if user_match:
    #         return user_match.group("number")

    def build_node(
        self, data: Dict, type_class: Message | Input | HTTPRequest
    ) -> Message | Input | HTTPRequest:
        return type_class.deserialize(data)

    @property
    def node(self) -> Message | Input | HTTPRequest | None:

        node = self.menu.get_node_by_id(node_id=self.context)

        if node.type == "message":
            node = self.build_node(node.serialize(), Message)
        elif node.type == "input":
            node = self.build_node(node.serialize(), Input)
        elif node.type == "http_request":
            node = self.build_node(node.serialize(), HTTPRequest)
        else:
            return

        return node

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
            await user.load_variables()
            return user

        if create:
            user = cls(user_id=user_id, context="m1")
            await user.insert()
            user = cast(cls, await super().get_by_user_id(user_id))
            user._add_to_cache()
            await user.load_variables()
            return user

    async def get_varibale(self, variable_id: str) -> Variable | None:
        """This function returns a variable object from the database if it exists,
        otherwise it returns None

        Parameters
        ----------
        variable_id : str
            The variable ID.

        Returns
        -------
            A variable object

        """
        try:
            return self.variables[variable_id]
        except KeyError:
            pass

        variable = await Variable.get(fk_user=self.id, variable_id=variable_id)

        if not variable:
            return

        return variable

    async def set_variable(self, variable_id: str, value: Any):
        """It creates a new variable object, adds it to the user's variables dictionary,
        and then inserts it into the database

        Parameters
        ----------
        variable_id : str
            The variable's name.
        value : Any
            The value of the variable.

        """
        variable = await Variable.get(variable_id=variable_id, fk_user=self.id)

        if variable is None:
            variable = Variable(variable_id, value, self.id)
            await variable.insert()
        else:
            await variable.update(variable_id=variable_id, value=value)

        self.variables_data[variable_id] = value
        self.variables[variable_id] = variable

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
        await self.update(context=context, state=state)
        self._add_to_cache()
