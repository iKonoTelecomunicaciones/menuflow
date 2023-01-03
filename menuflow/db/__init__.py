from mautrix.util.async_db import Database

from .client import Client
from .migrations import upgrade_table
from .room import Room
from .user import User


def init(db: Database) -> None:
    for table in (Room, User, Client):
        table.db = db


__all__ = ["upgrade_table", "Room", "User", "Client"]
