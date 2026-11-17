"""Compatibility contracts for the mautrix APIs used across Menuflow."""

from __future__ import annotations

import inspect

import pytest
from mautrix.client import Client
from mautrix.errors import MatrixInvalidToken
from mautrix.errors.request import MForbidden, MLimitExceeded, MNotFound
from mautrix.types import (
    Format,
    LocationInfo,
    LocationMessageEventContent,
    MessageEvent,
    MessageType,
    Obj,
    RoomID,
    SerializableAttrs,
    SerializableEnum,
    StateEvent,
    TextMessageEventContent,
    UserID,
)
from mautrix.util.async_db import Database, UpgradeTable
from mautrix.util.async_getter_lock import async_getter_lock
from mautrix.util.config import BaseFileConfig, ConfigUpdateHelper, RecursiveDict
from mautrix.util.magic import mimetype

from menuflow.config import Config
from menuflow.db.migrations import upgrade_table


def test_text_message_roundtrip():
    content = TextMessageEventContent(msgtype=MessageType.TEXT, body="hola")
    content.format = Format.HTML
    content.formatted_body = "<b>hola</b>"
    data = content.serialize()
    restored = TextMessageEventContent.deserialize(data)
    assert restored.body == "hola"
    assert restored.format == Format.HTML
    assert restored.formatted_body == "<b>hola</b>"


def test_location_message_roundtrip():
    content = LocationMessageEventContent(
        msgtype=MessageType.LOCATION,
        body="geo",
        geo_uri="geo:4.6,-74.0",
        info=LocationInfo(),
    )
    data = content.serialize()
    restored = LocationMessageEventContent.deserialize(data)
    assert restored.geo_uri == "geo:4.6,-74.0"


def test_message_and_state_event_roundtrip():
    msg = MessageEvent.deserialize(
        {
            "type": "m.room.message",
            "event_id": "$evt",
            "sender": "@u:example.com",
            "origin_server_ts": 1,
            "room_id": "!r:example.com",
            "content": {"msgtype": "m.text", "body": "hi"},
        }
    )
    assert msg.content.body == "hi"
    assert MessageEvent.deserialize(msg.serialize()).event_id == "$evt"

    state = StateEvent.deserialize(
        {
            "type": "m.room.member",
            "event_id": "$st",
            "sender": "@u:example.com",
            "origin_server_ts": 1,
            "room_id": "!r:example.com",
            "state_key": "@u:example.com",
            "content": {"membership": "join"},
        }
    )
    assert state.state_key == "@u:example.com"
    assert StateEvent.deserialize(state.serialize()).event_id == "$st"


def test_serializable_enum_and_obj():
    class Sample(SerializableEnum):
        A = "a"
        B = "b"

    assert Sample.A.value == "a"
    assert Sample.deserialize("b") == Sample.B
    assert Sample.A.serialize() == "a"

    obj = Obj(foo="bar", nested=Obj(x=1))
    assert obj["foo"] == "bar"
    assert obj.nested.x == 1


def test_config_load_and_recursive_dict(config: Config):
    assert isinstance(config, BaseFileConfig)
    assert config["homeserver.domain"] == "dominiocliente.com"
    assert config["menuflow.database"].startswith("postgresql://")
    helper = ConfigUpdateHelper(RecursiveDict({"a": {"b": 1}}), RecursiveDict({"a": {"b": 2}}))
    assert helper.base["a"]["b"] == 1
    assert helper.source["a"]["b"] == 2
    nested = RecursiveDict({"menuflow": {"openai": {"file_expiry_seconds": 3600}}})
    assert nested.get("menuflow.openai.file_expiry_seconds", None) == 3600


def test_upgrade_table_registers_migrations():
    assert isinstance(upgrade_table, UpgradeTable)
    assert len(upgrade_table.upgrades) >= 1
    sig = inspect.signature(Database.create)
    for name in ("url", "upgrade_table", "db_args", "log"):
        assert name in sig.parameters


@pytest.mark.parametrize(
    "method_name",
    [
        "send_text",
        "send_message_event",
        "download_media",
        "upload_media",
        "join_room",
        "invite_user",
        "get_state_event",
        "whoami",
    ],
)
def test_client_methods_exist(method_name: str):
    assert callable(getattr(Client, method_name))
    inspect.signature(getattr(Client, method_name))


def test_matrix_errors_hierarchy():
    assert issubclass(MLimitExceeded, Exception)
    assert issubclass(MNotFound, Exception)
    assert issubclass(MForbidden, Exception)
    assert issubclass(MatrixInvalidToken, Exception)


def test_magic_mimetype_and_async_getter_lock():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0c"
        b"IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    assert mimetype(png) == "image/png"
    assert callable(async_getter_lock)


def test_room_id_and_user_id_types():
    room_id = RoomID("!foo:example.com")
    user_id = UserID("@foo:example.com")
    assert str(room_id).startswith("!")
    assert str(user_id).startswith("@")


def test_serializable_attrs_available():
    assert issubclass(SerializableAttrs, object)
