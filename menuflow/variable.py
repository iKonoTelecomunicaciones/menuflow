from __future__ import annotations

from typing import Any, List, cast

from .db.variable import Variable as DBVariable


class Variable(DBVariable):
    def __init__(self, variable_id: str, value: Any, fk_user: int | None) -> None:
        super().__init__(variable_id=variable_id, value=value, fk_user=fk_user)

    @classmethod
    async def get(cls, fk_user: int, variable_id: str) -> Variable:
        variable = await cast(cls, await super().get(fk_user, variable_id))

        if variable is not None:
            return variable

    @classmethod
    async def create(cls, variable_id: str, value: Any, fk_user: int) -> Variable:
        variable = cls(variable_id, value, fk_user)
        await variable.insert()
        return variable

    @classmethod
    async def all_variables_by_fk_user(cls, fk_user: int) -> List[Variable] | None:
        return await super().get_all_variables_by_fk_user(fk_user=fk_user)
