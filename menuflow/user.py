from __future__ import annotations

from typing import Any, Dict, cast

from mautrix.types import UserID

from .db.user import User as DBUser
from .variable import Variable


class User(DBUser):

    by_user_id: Dict[UserID, "User"] = {}
    variables: Dict[str, Any] = {}

    def __init__(self, user_id: UserID, context: str, state: str) -> None:
        super().__init__(user_id=user_id, context=context, state=state)

    def _add_to_cache(self) -> None:
        if self.user_id:
            self.by_user_id[self.user_id] = self

    async def save(self) -> None:
        self._add_to_cache()
        await self.update()

    async def load_variables(self):
        for variable in await Variable.all_variables_by_fk_user(self.id):
            self.variables[variable.variable_id] = variable.value

    # @property
    # def phone(self) -> str | None:
    #     user_match = match("^@(?P<user_prefix>.+)_(?P<number>[0-9]{8,}):.+$", self.user_id)
    #     if user_match:
    #         return user_match.group("number")

    @classmethod
    async def get_by_user_id(cls, user_id: UserID, create: bool = True) -> "User" | None:
        try:
            return cls.by_user_id[user_id]
        except KeyError:
            pass

        user = cast(cls, await super().get_by_user_id(user_id))

        if user is not None:
            user._add_to_cache()
            user.load_variables()
            return user

        if create:
            user = cls(user_id, "message_1", "SHOW_MESSAGE")
            await user.insert()
            user._add_to_cache()
            user.load_variables()
            return user
