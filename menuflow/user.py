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
        id: int = None,
    ) -> None:
        super().__init__(id=id, mxid=mxid)
        self.log = self.log.getChild(self.mxid)

    def _add_to_cache(self) -> None:
        if self.mxid:
            self.by_mxid[self.mxid] = self

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
            user = cls(mxid=mxid)

            await user.insert()
            user = cast(cls, await super().get_by_mxid(mxid))
            user._add_to_cache()
            return user
