"""Compatibility contracts for jinja2 and jinja2-ansible-filters."""

from __future__ import annotations

import pytest
from jinja2 import TemplateSyntaxError, UndefinedError
from jinja2.exceptions import UndefinedError as UndefinedErrorAlias

from menuflow.jinja.env import jinja_env
from menuflow.utils import Util


def test_do_loopcontrols_and_debug_extensions():
    out = jinja_env.from_string(
        "{% set items = [] %}{% do items.append(1) %}"
        "{% for i in [1, 2, 3] %}{% if i == 2 %}{% break %}{% endif %}{{ i }}"
        "{% endfor %}{{ items | to_json }}"
    ).render()
    assert "1" in out
    assert "[1]" in out


def test_ansible_filters_available():
    for name in ("to_json", "from_json", "regex_replace", "b64encode"):
        assert name in jinja_env.filters

    rendered = jinja_env.from_string(
        "{{ {'a': 1} | to_json }}|{{ '{\"b\":2}' | from_json }}|"
        "{{ 'hello' | regex_replace('l+', 'L') }}|{{ 'ab' | b64encode }}"
    ).render()
    assert '"a": 1' in rendered or '"a":1' in rendered.replace(" ", "")
    assert "b" in rendered
    assert "heLo" in rendered
    assert "YWI=" in rendered


def test_menuflow_filters_globals_and_tests_registered():
    assert "strftime_tz" in jinja_env.filters
    assert "compare_ratio" in jinja_env.globals
    assert "odd" in jinja_env.tests
    assert "even" in jinja_env.tests


def test_template_syntax_error_exposes_fields_used_by_menuflow():
    with pytest.raises(TemplateSyntaxError) as exc_info:
        jinja_env.from_string("{{ a ")
    err = exc_info.value
    assert isinstance(err.lineno, int)
    assert err.message
    # Util.jinja_render reads e.name, e.lineno and e.message
    _ = err.name


def test_undefined_error_is_raised_for_strict_undefined_paths():
    # Default Environment is not StrictUndefined, so missing vars render empty.
    # Util still imports and catches UndefinedError from filters/globals that raise it.
    assert UndefinedError is UndefinedErrorAlias

    def boom():
        raise UndefinedError("missing")

    jinja_env.globals["_compat_boom"] = boom
    try:
        with pytest.raises(UndefinedError):
            jinja_env.from_string("{{ _compat_boom() }}").render()
    finally:
        jinja_env.globals.pop("_compat_boom", None)


def test_util_jinja_render_and_recursive_render():
    assert Util.jinja_render("Hello {{ name }}", {"name": "Ada"}) == "Hello Ada"
    assert Util.jinja_render("{{ route.city }}", {"route": {"city": "Bogota"}}) == "Bogota"

    nested = Util.recursive_render(
        {"greeting": "Hi {{ user }}", "nums": ["{{ n }}"]},
        {"user": "Bob", "n": "1"},
    )
    assert nested["greeting"] == "Hi Bob"
    assert nested["nums"] == ["1"]

    # Both delimiters must be present for Util to attempt rendering; syntax errors
    # then return None when return_errors=False (same path as TemplateSyntaxError).
    assert Util.jinja_render("{{ a | }}", {}, return_errors=False) is None
