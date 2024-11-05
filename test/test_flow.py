import nest_asyncio
import pytest

nest_asyncio.apply()

from menuflow.flow import Flow
from menuflow.room import Room


# @pytest.mark.asyncio
class TestFlow:
    def test_check_data(self, sample_flow_1: Flow):
        assert bool(sample_flow_1.data) == True

    def test_get_node_by_id(self, sample_flow_1: Flow):
        node = sample_flow_1.get_node_by_id("request-1")
        assert node.get("id") == "request-1"

    def test_get_middleware_by_id(self, sample_flow_1: Flow):
        pass

    def test_node_by_room(self, sample_flow_1: Flow, room: Room):
        node = sample_flow_1.node(room)
        assert node.id == "start"

    def test_flow_variables(self, sample_flow_1: Flow):
        assert sample_flow_1.flow_variables == {
            "flow": {"cat_fatc_url": "https://catfact.ninja/fact"}
        }

    def test_dont_repeat_nodes(self, sample_flow_1: Flow, sample_flow_2: Flow):
        assert sample_flow_1.nodes != sample_flow_2.nodes
        assert sample_flow_1.data != sample_flow_2.data
        assert sample_flow_1.get_node_by_id("input-1") != sample_flow_2.get_node_by_id("input-1")
