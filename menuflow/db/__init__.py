from mautrix.util.async_db import Database

from .client import Client
from .flow import Flow
from .flow_backup import FlowBackup
from .migrations import upgrade_table
from .module import Module
from .room import Room
from .route import Route
from .user import User
from .webhook import Webhook
from .webhook_queue import WebhookQueue


def init(db: Database) -> None:
    for table in (Room, User, Client, Route, Flow, FlowBackup, Webhook, Module, WebhookQueue):
        table.db = db


__all__ = [
    "upgrade_table",
    "Room",
    "User",
    "Client",
    "Route",
    "Flow",
    "FlowBackup",
    "Webhook",
    "Module",
    "WebhookQueue",
]
