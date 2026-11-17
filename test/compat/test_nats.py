"""Compatibility contracts for nats-py (no live server)."""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

import nats
import pytest
from nats.errors import BadSubjectError
from nats.js.api import RetentionPolicy, StreamConfig
from nats.js.client import JetStreamContext
from nats.js.errors import Error, NotFoundError

from menuflow.events.nats_publisher import NatsPublisher


def test_nats_connect_accepts_menuflow_options():
    sig = inspect.signature(nats.connect)
    # Positional servers plus kwargs used by NatsPublisher.
    assert "servers" in sig.parameters
    # Options are **options; verify they are accepted at call-binding time.
    bound = sig.bind_partial(
        "nats://localhost:4222",
        allow_reconnect=True,
        max_reconnect_attempts=3,
        user="user",
        password="pass",
        name="MENUFLOW example user",
    )
    assert bound.kwargs["allow_reconnect"] is True
    assert bound.kwargs["max_reconnect_attempts"] == 3
    assert bound.kwargs["user"] == "user"
    assert bound.kwargs["password"] == "pass"
    assert "MENUFLOW" in bound.kwargs["name"]


def test_stream_config_and_retention_policies():
    config = StreamConfig(
        name="CEP",
        subjects=["cep.*"],
        retention=RetentionPolicy.WORK_QUEUE,
        num_replicas=1,
        max_age=24 * 60 * 60,
    )
    assert config.name == "CEP"
    assert config.subjects == ["cep.*"]
    assert config.retention == RetentionPolicy.WORK_QUEUE
    assert RetentionPolicy.INTEREST is not None
    assert config.max_age == 86400


def test_menuflow_subject_patterns_are_valid():
    """nats-py 2.16 validates subjects client-side; keep Menuflow patterns legal."""
    subjects = ["menuflow_cep.*", "menuflow_mntr.*", "cep.*", "mntr.>"]
    for subject in subjects:
        # Empty tokens / misplaced wildcards raise BadSubjectError on newer clients.
        assert subject and ".." not in subject
        assert not subject.startswith(".") and not subject.endswith(".")
        assert "*" in subject or ">" in subject or subject.isidentifier() or "." in subject
    assert BadSubjectError is not None


def test_jetstream_methods_signatures():
    info_sig = inspect.signature(JetStreamContext.stream_info)
    assert "name" in info_sig.parameters
    assert "subjects_filter" in info_sig.parameters

    add_sig = inspect.signature(JetStreamContext.add_stream)
    assert "config" in add_sig.parameters

    update_sig = inspect.signature(JetStreamContext.update_stream)
    assert "config" in update_sig.parameters


def test_js_error_has_description_and_not_found_hierarchy():
    err = Error(description="stream not found")
    assert err.description == "stream not found"
    assert "stream not found" in err.description
    assert issubclass(NotFoundError, Error)


@pytest.mark.asyncio
async def test_stream_handler_creates_when_missing_and_updates_when_present():
    """Mirror NatsPublisher.stream_handler create/update branches without a live server."""
    created: list[StreamConfig] = []
    updated: list[StreamConfig] = []

    js = MagicMock()
    missing = StreamConfig(
        name="S_CEP", subjects=["s_cep.*"], retention=RetentionPolicy.WORK_QUEUE
    )
    existing = StreamConfig(
        name="S_MNTR",
        subjects=["s_mntr.*"],
        retention=RetentionPolicy.INTEREST,
        max_age=86400,
    )

    async def stream_info(name: str, subjects_filter: str | None = None):
        if name == missing.name:
            raise Error(description="stream not found")
        return MagicMock(config=existing)

    js.stream_info = AsyncMock(side_effect=stream_info)
    js.add_stream = AsyncMock(side_effect=lambda config: created.append(config))
    js.update_stream = AsyncMock(side_effect=lambda config: updated.append(config))

    await NatsPublisher.stream_handler(config_list=[missing, existing], js=js)

    assert [c.name for c in created] == ["S_CEP"]
    assert [c.name for c in updated] == ["S_MNTR"]
    js.stream_info.assert_any_await(name="S_CEP", subjects_filter="s_cep.*")
    js.stream_info.assert_any_await(name="S_MNTR", subjects_filter="s_mntr.*")
