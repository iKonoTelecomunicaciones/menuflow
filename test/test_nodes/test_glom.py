import nest_asyncio
import pytest
from glom import Path

nest_asyncio.apply()

from menuflow.utils import JQ2Glom


class TestJQ2Glom:
    """Test class for JQ2Glom utility class"""

    _jq2glom = JQ2Glom()

    def test_simple_attribute_path(self):
        """Test converting simple attribute paths"""
        assert self._jq2glom.to_glom_path("a") == Path("a")
        assert self._jq2glom.to_glom_path("a.b.c") == Path("a", "b", "c")

    def test_index_number_path(self):
        """Test converting index number paths"""
        assert self._jq2glom.to_glom_path("a[0]") == Path("a", 0)
        assert self._jq2glom.to_glom_path("a.b[1].c") == Path("a", "b", 1, "c")

    def test_key_string_path(self):
        """Test converting key string paths"""
        assert self._jq2glom.to_glom_path('a["0"]') == Path("a", "0")
        assert self._jq2glom.to_glom_path('a["123"].b') == Path("a", "123", "b")

    def test_key_string_regular_path(self):
        """Test converting key string regular paths"""
        assert self._jq2glom.to_glom_path('a.b["foo"].c') == Path("a", "b", "foo", "c")
        assert self._jq2glom.to_glom_path('a["line\nfeed"].b') == Path("a", "line\nfeed", "b")

    def test_combined_attributes_indices_keys_path(self):
        """Test converting combined attributes, indices, and keys paths"""
        assert self._jq2glom.to_glom_path('a["with space"].b') == Path("a", "with space", "b")
        assert self._jq2glom.to_glom_path('a["with:colon"].b') == Path("a", "with:colon", "b")
        assert self._jq2glom.to_glom_path('a["with.dot"].b') == Path("a", "with.dot", "b")

    def test_jinja_syntax_path(self):
        """Test converting Jinja syntax paths"""
        assert self._jq2glom.to_glom_path("a.b.0") == Path("a", "b", 0)
        assert self._jq2glom.to_glom_path("0") == Path(0)
        assert self._jq2glom.to_glom_path("a.1.b") == Path("a", 1, "b")

    def test_complex_path(self):
        """Test converting complex paths"""
        assert self._jq2glom.to_glom_path("a[0].b[1].c[2]") == Path("a", 0, "b", 1, "c", 2)
        assert self._jq2glom.to_glom_path('a["key.with.dot"].b') == Path("a", "key.with.dot", "b")
        assert self._jq2glom.to_glom_path('a["key with space"].b') == Path(
            "a", "key with space", "b"
        )
        assert self._jq2glom.to_glom_path('a["key-with-dash"].b') == Path(
            "a", "key-with-dash", "b"
        )
        assert self._jq2glom.to_glom_path('a["key_with_underscore"].b') == Path(
            "a", "key_with_underscore", "b"
        )
        assert self._jq2glom.to_glom_path('d["key.with.dot"].1.a["b.1"]["b\\c"].2') == Path(
            "d", "key.with.dot", 1, "a", "b.1", "b\\c", 2
        )

    def test_example_jq(self):
        """Test converting example JQ paths"""
        assert self._jq2glom.to_glom_path('a["key.with.dot"].b') == Path("a", "key.with.dot", "b")
        assert self._jq2glom.to_glom_path('d.1.a["b.1"]["b\\c"].2') == Path(
            "d", 1, "a", "b.1", "b\\c", 2
        )
        assert self._jq2glom.to_glom_path('a."1".d."b.1".c.0."d.2"') == Path(
            "a", "1", "d", "b.1", "c", 0, "d.2"
        )

    def test_additional_examples(self):
        """Test converting additional examples"""
        assert self._jq2glom.to_glom_path('d.1.a["b.1"]["b\\c"].2') == Path(
            "d", 1, "a", "b.1", "b\\c", 2
        )
        assert self._jq2glom.to_glom_path('a."1".d."b.1".c.0."d.2"') == Path(
            "a", "1", "d", "b.1", "c", 0, "d.2"
        )
