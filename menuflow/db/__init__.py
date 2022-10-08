from mautrix.util.async_db import Database

from .client import Client
from .migrations import upgrade_table
from .user import User


def init(db: Database) -> None:
    for table in (User, Client):
        table.db = db


__all__ = ["upgrade_table", "User", "Client"]
