"""Compatibility contracts for nats-py (no live server)."""

from __future__ import annotations

import inspect

import nats
from nats.js.api import RetentionPolicy, StreamConfig
from nats.js.client import JetStreamContext
from nats.js.errors import Error, NotFoundError


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
