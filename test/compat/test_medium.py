"""Medium-risk dependency behaviour used by Menuflow."""

from __future__ import annotations

import inspect
import warnings
from datetime import date, datetime
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import holidays
import pytest
from aiosmtplib import SMTP
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPConnectTimeoutError,
    SMTPServerDisconnected,
)
from babel import Locale
from glom import Delete, Path, PathAccessError, assign, glom, merge
from glom.mutation import PathDeleteError
from mautrix.util.config import RecursiveDict
from phonenumbers import PhoneNumberFormat, carrier, format_number, geocoder, is_valid_number
from phonenumbers import parse as parse_phone
from phonenumbers import timezone
from pycountry import countries
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from menuflow.config import Config
from menuflow.email_client import Email, EmailClient
from menuflow.jinja.jinja_filters.phone_numbers import PhoneNumbers
from menuflow.utils import JQ2Glom, Util


def test_glom_assign_delete_and_merge():
    data: dict = {}
    assign(data, Path("route", "a", "b"), 1, missing=dict)
    assert data == {"route": {"a": {"b": 1}}}

    # Room.get_variable catches PathAccessError on missing reads.
    with pytest.raises(PathAccessError):
        glom(data, Path("route", "missing"))

    # Delete of an existing leaf works; missing keys raise PathDeleteError.
    glom(data, Delete(Path("route", "a", "b")))
    assert data == {"route": {"a": {}}}
    with pytest.raises(PathDeleteError):
        glom(data, Delete(Path("route", "x")))

    merged = glom([{"a": 1}, {"b": 2}], merge)
    assert merged == {"a": 1, "b": 2}


def test_jq2glom_typical_paths():
    converter = JQ2Glom()
    assert converter.to_glom_path("route.user.name") == Path("route", "user", "name")
    assert converter.to_glom_path("items[0].id") == Path("items", 0, "id")


def test_jq_compile_status_boundaries():
    ok = Util.jq_compile(".a", {"a": 1})
    assert ok == {"result": [1], "error": None, "status": 200}

    compile_error = Util.jq_compile("..[", {})
    assert compile_error["status"] == 400
    assert compile_error["error"]
    assert compile_error["result"] == []

    runtime_error = Util.jq_compile(".a | tonumber", {"a": "x"})
    assert runtime_error["status"] == 421
    assert runtime_error["error"]
    assert runtime_error["result"] == []


def test_ruamel_commented_map_with_recursive_dict():
    commented = CommentedMap({"headers": CommentedMap({"Authorization": "Bearer x"})})
    commented["headers"]["X-Extra"] = "1"
    nested = RecursiveDict({"middleware": commented})
    assert nested["middleware"]["headers"]["Authorization"] == "Bearer x"
    assert nested["middleware"]["headers"]["X-Extra"] == "1"
    assert isinstance(commented, dict)


def test_ruamel_roundtrip_and_middleware_pattern():
    """Config/middleware path: YAML rt load + CommentedMap(**dict) like HTTP middleware."""
    yaml = YAML(typ="rt")
    raw = "menuflow:\n  database: postgresql://x\n  timeouts:\n    http_request: 30\n"
    loaded = yaml.load(raw)
    assert loaded["menuflow"]["timeouts"]["http_request"] == 30

    out = StringIO()
    yaml.dump(loaded, out)
    assert "postgresql://x" in out.getvalue()

    # Middlewares wrap JSON bodies as RecursiveDict(CommentedMap(**response_data)).
    response_data = {"token": "abc", "nested": {"ok": True}}
    serialized = RecursiveDict(CommentedMap(**response_data))
    assert serialized["token"] == "abc"
    assert serialized["nested"]["ok"] is True


def test_aiosmtplib_smtp_signature_and_errors():
    sig = inspect.signature(SMTP.__init__)
    # Email client constructs SMTP and uses these exception classes.
    assert SMTPAuthenticationError is not None
    assert SMTPConnectTimeoutError is not None
    assert SMTPServerDisconnected is not None
    assert "hostname" in sig.parameters
    assert "port" in sig.parameters
    assert "username" in sig.parameters
    assert "password" in sig.parameters
    assert "use_tls" in sig.parameters or "start_tls" in sig.parameters


@pytest.mark.asyncio
async def test_email_client_login_and_send_reconnects_on_disconnect():
    """Exercise EmailClient against aiosmtplib the way production constructs SMTP."""
    client = EmailClient(
        server_id="smtp-1",
        host="smtp.example.com",
        port="587",
        username="bot@example.com",
        password="secret",
        start_tls=True,
    )
    smtp = MagicMock()
    smtp.connect = AsyncMock()
    smtp.ehlo = AsyncMock()
    smtp.sendmail = AsyncMock(side_effect=[SMTPServerDisconnected("gone"), None])
    smtp.is_connected = True

    with patch("menuflow.email_client.SMTP", return_value=smtp) as smtp_cls:
        await client.login()
        smtp_cls.assert_called_once_with(
            hostname="smtp.example.com",
            port="587",
            username="bot@example.com",
            password="secret",
            start_tls=True,
        )
        smtp.connect.assert_awaited()
        smtp.ehlo.assert_awaited()

        email = Email(subject="hi", text="<p>body</p>", recipients=["a@example.com"])
        await client.send_email(email)

    assert smtp.sendmail.await_count == 2
    assert smtp.connect.await_count == 2


def test_phonenumbers_colombia_contract():
    number = parse_phone("+573001234567")
    assert is_valid_number(number)
    assert format_number(number, PhoneNumberFormat.E164) == "+573001234567"
    assert timezone.time_zones_for_number(number)
    # Carrier/geocoder may be empty depending on metadata, but callables must exist.
    _ = carrier.name_for_number(number, "es")
    _ = geocoder.description_for_number(number, "es")

    wrapped = PhoneNumbers("+573001234567")
    assert wrapped.is_valid_number is True
    assert wrapped.format_for_number_e164 == "+573001234567"


def test_holidays_subdiv_preferred_and_prov_none_safe():
    sig = inspect.signature(holidays.country_holidays)
    assert "subdiv" in sig.parameters

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        # Preferred API for Menuflow going forward.
        via_subdiv = holidays.country_holidays("CO", subdiv=None)
        assert date(2025, 12, 25) in via_subdiv
        # Current Util.is_holiday still passes prov=; None must not warn.
        via_prov = holidays.country_holidays("CO", prov=None)
        assert date(2025, 12, 25) in via_prov
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecations, f"Unexpected DeprecationWarning: {deprecations}"


def test_util_is_holiday_and_country_helpers():
    assert Util.is_holiday(datetime(2025, 12, 25), "CO", None) is True
    assert Util.is_holiday(datetime(2025, 12, 24), "CO", None) is False
    # Unknown country codes must not raise; Util catches NotImplementedError.
    assert Util.is_holiday(datetime(2025, 12, 25), "ZZ", None) is False

    country = countries.get(alpha_2="CO")
    assert country is not None
    assert country.alpha_2 == "CO"

    supported = holidays.list_supported_countries(include_aliases=False)
    assert "CO" in supported
    assert Locale("es").territories.get("CO")


@pytest.mark.asyncio
async def test_util_get_countries_returns_entries(config: Config):
    util = Util(config)
    result = await util.get_countries("es")
    assert isinstance(result, dict)
    assert "CO" in result["countries"]
    assert result["labels"]
