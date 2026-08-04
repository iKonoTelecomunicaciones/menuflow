import json
import sys
import types
from unittest.mock import MagicMock

import pytest_asyncio
from pytest_mock import MockerFixture

from menuflow.config import Config
from menuflow.db import Route
from menuflow.flow import Flow
from menuflow.nodes import Base, Input, Location, Message, Switch
from menuflow.room import Room
from menuflow.utils import Util

fake_version = types.ModuleType("menuflow.version")
fake_version.version = "test"
sys.modules.setdefault("menuflow.version", fake_version)

from menuflow.web.base import set_config


async def _update_variables_no_db(self) -> None:
    """Persist room variables to the JSON string without touching the DB."""
    self.flush_vars()
    self.clear_vars_cache()


async def _update_route_variables_no_db(self) -> None:
    """Simulates JSONB: normalizes keys and types like in the DB."""
    self.variables = json.loads(json.dumps(self.variables))


@pytest_asyncio.fixture(autouse=True)
async def register_web_config(config: Config) -> None:
    set_config(config=config, flow_utils=MagicMock())


@pytest_asyncio.fixture
async def config() -> Config:
    _config = Config(
        path="menuflow/example-config.yaml",
        base_path="menuflow",
    )
    _config.load()
    return _config


@pytest_asyncio.fixture
async def sample_flow_1(config: Config) -> Flow:
    flow = Flow()
    flow_example = Util.flow_example(flow_index=0).get("menu")
    flow_vars = flow_example.get("flow_variables", {})
    nodes = flow_example.get("nodes", [])
    await flow.load_flow(
        content={"flow_variables": flow_vars, "nodes": nodes, "loaded_metadata": {}}, config=config
    )
    for node in [Input, Location, Message, Switch]:
        node.config = config

    return flow


@pytest_asyncio.fixture
async def sample_flow_2(config: Config) -> Flow:
    flow = Flow()
    flow_example = Util.flow_example(flow_index=1).get("menu")
    flow_vars = flow_example.get("flow_variables", {})
    nodes = flow_example.get("nodes", [])
    await flow.load_flow(
        content={"flow_variables": flow_vars, "nodes": nodes, "loaded_metadata": {}}, config=config
    )
    for node in [Input, Location, Message, Switch]:
        node.config = config

    return flow


@pytest_asyncio.fixture
async def route(mocker: MockerFixture) -> Route:
    mocker.patch.object(Route, "update")
    mocker.patch.object(Route, "update_variables", _update_route_variables_no_db)
    return Route(room=1, node_id="start", client="@foo:foo.com", variables={"route": {}})


@pytest_asyncio.fixture
async def room(mocker: MockerFixture, config: Config, route: Route) -> Room:
    mocker.patch.object(Room, "update")
    mocker.patch.object(Room, "update_variables", _update_variables_no_db)
    room = Room(room_id="!foo:foo.com")
    room.matrix_client = MagicMock()
    room.bot_mxid = "@foo:foo.com"
    room.route = route
    room.config = config
    return room


@pytest_asyncio.fixture
async def base(sample_flow_1: Flow, room: Room, mocker: MockerFixture) -> Base:
    mocker.patch.object(
        Base,
        "run",
    )
    base = Base(room=room, default_variables=sample_flow_1.flow_variables)
    return base


@pytest_asyncio.fixture
async def message(sample_flow_1: Flow, base: Base) -> Message:
    message_node_data = sample_flow_1.get_node_by_id("start")
    message_node = Message(
        message_node_data, room=base.room, default_variables=base.default_variables
    )
    return message_node


@pytest_asyncio.fixture
async def switch(sample_flow_1: Flow, base: Base) -> Switch:
    switch_node_data = sample_flow_1.get_node_by_id("switch-1")
    switch_node = Switch(
        switch_node_data, room=base.room, default_variables=base.default_variables
    )
    return switch_node


@pytest_asyncio.fixture
async def input_text(sample_flow_1: Flow, base: Base) -> Input:
    input_node_data = sample_flow_1.get_node_by_id("input-1")
    input_node = Input(input_node_data, room=base.room, default_variables=base.default_variables)
    return input_node


@pytest_asyncio.fixture
async def input_media(sample_flow_1: Flow, base: Base) -> Input:
    input_node_data = sample_flow_1.get_node_by_id("input-4")
    input_node = Input(input_node_data, room=base.room, default_variables=base.default_variables)
    return input_node


@pytest_asyncio.fixture
async def location(sample_flow_1: Flow, base: Base) -> Location:
    location_node_data = sample_flow_1.get_node_by_id("location-1")
    location_node = Location(
        location_node_data, room=base.room, default_variables=base.default_variables
    )
    return location_node
