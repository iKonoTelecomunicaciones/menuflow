import pytest_asyncio
from mautrix.client import Client
from pytest_mock import MockerFixture

from menuflow import Flow, Room, Util
from menuflow.config import Config
from menuflow.nodes import Base, Input, Location, Message, Switch


@pytest_asyncio.fixture
async def config() -> Config:
    _config = Config(
        path="menuflow/example-config.yaml",
        base_path="menuflow",
    )
    _config.load()
    return _config


@pytest_asyncio.fixture
async def flow(config: Config) -> Flow:
    flow = Flow(Util.flow_example().get("menu"))
    flow.load()

    for node in [Input, Location, Message, Switch]:
        node.config = config

    return flow


@pytest_asyncio.fixture
async def room(mocker: MockerFixture) -> Room:
    mocker.patch.object(
        Room,
        "update",
    )
    return Room(room_id="!foo:foo.com", node_id="start")


@pytest_asyncio.fixture
async def base(flow: Flow, room: Room, mocker: MockerFixture) -> Base:
    mocker.patch.object(
        Base,
        "run",
    )
    base = Base()
    base.room = room
    base.variables = flow.flow_variables
    return base


@pytest_asyncio.fixture
async def message(flow: Flow, base: Base) -> Message:
    message_node = flow.get_node_by_id("start")
    message_node.room = base.room
    message_node.variables = base.variables
    message_node.matrix_client = Client(base_url="")
    return message_node


@pytest_asyncio.fixture
async def switch(flow: Flow, base: Base) -> Switch:
    switch_node = flow.get_node_by_id("switch-1")
    switch_node.room = base.room
    switch_node.variables = base.variables
    switch_node.matrix_client = Client(base_url="")
    return switch_node


@pytest_asyncio.fixture
async def input_text(flow: Flow, base: Base) -> Input:
    input_node = flow.get_node_by_id("input-1")
    input_node.room = base.room
    input_node.variables = base.variables
    input_node.matrix_client = Client(base_url="")
    return input_node


@pytest_asyncio.fixture
async def input_media(flow: Flow, base: Base) -> Input:
    input_node = flow.get_node_by_id("input-4")
    input_node.room = base.room
    input_node.variables = base.variables
    input_node.matrix_client = Client(base_url="")
    return input_node


@pytest_asyncio.fixture
async def location(flow: Flow, base: Base) -> Location:
    location_node = flow.get_node_by_id("location-1")
    location_node.room = base.room
    location_node.variables = base.variables
    location_node.matrix_client = Client(base_url="")
    return location_node
