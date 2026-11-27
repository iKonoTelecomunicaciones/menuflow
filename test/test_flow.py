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
            "flow": {
                "cat_fatc_url": "https://catfact.ninja/fact",
                "cat_name": "Luffy",
                "str_number": "61481488798",
                "number": 87684525412,
                "counter": 10,
                "dictionary": {"key": "value"},
                "bool": True,
                "bool_str": "true",
                "none_str": "None",
                "none": None,
                "multiple_lines": "line 1\nline 2\nline 3",
            },
        }

    def test_dont_repeat_nodes(self, sample_flow_1: Flow, sample_flow_2: Flow):
        assert sample_flow_1.nodes != sample_flow_2.nodes
        assert sample_flow_1.data != sample_flow_2.data
        assert sample_flow_1.get_node_by_id("input-1") != sample_flow_2.get_node_by_id("input-1")

    def test_validate_functions_missing_name(self):
        errors, _warnings = Flow.validate_functions(
            [{"id": "fn1", "type": "function", "o_connection": "x"}]
        )
        assert any("missing required field 'name'" in e for e in errors)

    def test_validate_functions_duplicate_name(self):
        errors, _warnings = Flow.validate_functions(
            [
                {"id": "fn1", "type": "function", "name": "dup", "o_connection": "a"},
                {"id": "fn2", "type": "function", "name": "dup", "o_connection": "b"},
            ]
        )
        assert any("Duplicate function name" in e for e in errors)

    def test_get_function_by_name_and_id(self, sample_flow_1: Flow):
        sample_flow_1.nodes.append(
            {"id": "fn_x", "type": "function", "name": "my_fn", "o_connection": "start"}
        )
        sample_flow_1.functions_by_name = sample_flow_1._build_functions_by_name(
            sample_flow_1.nodes
        )
        assert sample_flow_1.get_function("my_fn")["id"] == "fn_x"
        assert sample_flow_1.get_function("fn_x")["id"] == "fn_x"
        assert sample_flow_1.get_function("missing") is None
