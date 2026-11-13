"""Basic smoke/behaviour checks for lower-risk dependencies."""

from __future__ import annotations

import io
from datetime import datetime

import pytest
from fuzzywuzzy import fuzz
from markdown import markdown
from mautrix.util.magic import mimetype
from PIL import Image
from pytz import timezone
from yarl import URL


def _assert_markdown():
    html = markdown("**a**")
    assert "<strong>a</strong>" in html


def _assert_pytz():
    bogota = timezone("America/Bogota")
    offset = bogota.utcoffset(datetime(2024, 1, 15, 12, 0, 0))
    assert offset.total_seconds() == -5 * 3600


def _assert_pillow():
    image = Image.new("RGB", (8, 8), color=(255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    assert buffer.getvalue()[:8] == b"\x89PNG\r\n\x1a\n"


def _assert_magic():
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0c"
        b"IDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    assert mimetype(png) == "image/png"


def _assert_fuzzywuzzy_levenshtein():
    assert fuzz.ratio("hola", "hola") == 100
    # python-Levenshtein should be the active backend for speed/accuracy.
    import Levenshtein

    assert Levenshtein.ratio("hola", "hola") == 1.0


def _assert_yarl():
    url = URL("https://example.com/path").with_query({"q": "1"})
    assert str(url) == "https://example.com/path?q=1"
    assert url.query["q"] == "1"


@pytest.mark.parametrize(
    ("package", "check"),
    [
        ("Markdown", _assert_markdown),
        ("pytz", _assert_pytz),
        ("pillow", _assert_pillow),
        ("python-magic", _assert_magic),
        ("fuzzywuzzy+python-Levenshtein", _assert_fuzzywuzzy_levenshtein),
        ("yarl", _assert_yarl),
    ],
)
def test_basic_dependency(package: str, check):
    check()
