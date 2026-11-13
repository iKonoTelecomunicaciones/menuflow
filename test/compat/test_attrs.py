"""Compatibility contracts for attrs + SerializableAttrs used by flow models."""

from __future__ import annotations

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from menuflow.repository.flow import Flow
from menuflow.utils import Util


@dataclass
class SampleModel(SerializableAttrs):
    name: str = ib(default="")
    count: int = ib(default=0)
    tags: list[str] = ib(factory=list)
    meta: dict = ib(factory=dict, metadata={"json": "meta"})


def test_dataclass_ib_serialize_deserialize_roundtrip():
    model = SampleModel(name="flow", count=2, tags=["a", "b"], meta={"x": 1})
    data = model.serialize()
    restored = SampleModel.deserialize(data)
    assert restored.name == "flow"
    assert restored.count == 2
    assert restored.tags == ["a", "b"]
    assert restored.meta["x"] == 1
    assert SampleModel.deserialize(restored.serialize()).name == "flow"


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
