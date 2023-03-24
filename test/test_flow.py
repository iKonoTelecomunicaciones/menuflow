import nest_asyncio
import pytest

nest_asyncio.apply()

from menuflow import Flow, Room


# @pytest.mark.asyncio
class TestFlow:
    def test_check_data(self, flow: Flow):
        assert bool(flow.data) == True

    def test_get_node_by_id(self, flow: Flow):
        node = flow.get_node_by_id("request-1")
        assert node.id == "request-1"

    def test_get_middleware_by_id(self, flow: Flow):
        pass

    def test_node_by_room(self, flow: Flow, room: Room):
        node = flow.node(room)
        assert node.id == "start"

    def test_flow_variables(self, flow: Flow):
        assert flow.flow_variables == {"cat_fatc_url": "https://catfact.ninja/fact"}
