from mautrix.util.async_db import Database

from .migrations import upgrade_table
from .user import User
from .variable import Variable


def init(db: Database) -> None:
    for table in [User, Variable]:
        table.db = db


__all__ = ["upgrade_table", "User", "Variable"]
