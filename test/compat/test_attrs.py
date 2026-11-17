"""Compatibility contracts for attrs + SerializableAttrs used by flow models."""

from __future__ import annotations

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from menuflow.repository.flow import Flow
from menuflow.repository.nodes.http_request import HTTPRequest
from menuflow.repository.nodes.switch import Case, Switch
from menuflow.utils import Util


@dataclass
class SampleModel(SerializableAttrs):
    name: str = ib(default="")
    count: int = ib(default=0)
    tags: list[str] = ib(factory=list)
    meta: dict = ib(factory=dict, metadata={"json": "meta"})


@dataclass
class SampleChild(SampleModel):
    """Inheritance + defaults: sensitive to attrs 25.4+ kw_only changes."""

    extra: str = ib(default="")
    nested: dict = ib(factory=dict)


def test_dataclass_ib_serialize_deserialize_roundtrip():
    model = SampleModel(name="flow", count=2, tags=["a", "b"], meta={"x": 1})
    data = model.serialize()
    restored = SampleModel.deserialize(data)
    assert restored.name == "flow"
    assert restored.count == 2
    assert restored.tags == ["a", "b"]
    assert restored.meta["x"] == 1
    assert SampleModel.deserialize(restored.serialize()).name == "flow"


def test_attrs_inheritance_with_defaults_roundtrip():
    child = SampleChild(name="parent", count=1, tags=["t"], meta={"k": 1}, extra="x", nested={"a": 2})
    restored = SampleChild.deserialize(child.serialize())
    assert restored.name == "parent"
    assert restored.extra == "x"
    assert restored.nested["a"] == 2
    assert SampleChild.deserialize(restored.serialize()).serialize() == child.serialize()


def test_http_request_node_inherits_switch_roundtrip():
    """HTTPRequest subclasses Switch; attrs inheritance must keep cases/url intact."""
    node = HTTPRequest.deserialize(
        {
            "id": "r1",
            "type": "http_request",
            "method": "GET",
            "url": "https://example.com/{{q}}",
            "variables": {"news": "data"},
            "cases": [{"id": "200", "o_connection": "m1"}, {"id": "default", "o_connection": "m2"}],
        }
    )
    assert isinstance(node, Switch)
    assert node.method == "GET"
    assert node.url.endswith("{{q}}")
    assert len(node.cases) == 2
    first_case = node.cases[0]
    # SerializableAttrs may keep nested list items as dicts or Case instances.
    case_id = first_case.id if isinstance(first_case, Case) else first_case["id"]
    assert case_id == "200"
    roundtrip = HTTPRequest.deserialize(node.serialize())
    assert roundtrip.serialize() == node.serialize()


def test_flow_repository_loads_sample_flows():
    for index in (0, 1):
        example = Util.flow_example(flow_index=index)["menu"]
        flow = Flow.deserialize(
            {
                "nodes": example.get("nodes", []),
                "flow_variables": example.get("flow_variables", {}),
                "loaded_metadata": {},
            }
        )
        assert isinstance(flow.nodes, list)
        assert len(flow.nodes) >= 1
        assert flow.flow_variables is not None
        assert flow.serialize()["flow_variables"]
        roundtrip = Flow.deserialize(flow.serialize())
        assert roundtrip.serialize() == flow.serialize()
