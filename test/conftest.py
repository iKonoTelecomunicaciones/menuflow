from unittest.mock import MagicMock

import pytest_asyncio
from mautrix.client import Client
from pytest_mock import MockerFixture

from menuflow.config import Config
from menuflow.db import Route
from menuflow.flow import Flow
from menuflow.nodes import Base, Input, Location, Message, Switch
from menuflow.room import Room
from menuflow.utils import Util


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
    await flow.load_flow(content=Util.flow_example(flow_index=0), config=config)
    for node in [Input, Location, Message, Switch]:
        node.config = config

    return flow


@pytest_asyncio.fixture
async def sample_flow_2(config: Config) -> Flow:
    flow = Flow()
    await flow.load_flow(content=Util.flow_example(flow_index=1), config=config)
    for node in [Input, Location, Message, Switch]:
        node.config = config

    return flow


@pytest_asyncio.fixture
async def route(mocker: MockerFixture) -> Route:
    mocker.patch.object(
        Route,
        "update",
    )
    return Route(
        room=1,
        node_id="start",
        client="@foo:foo.com",
    )


@pytest_asyncio.fixture
async def room(mocker: MockerFixture, config: Config, route: Route) -> Room:
    mocker.patch.object(
        Room,
        "update",
    )
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
