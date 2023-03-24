import nest_asyncio

nest_asyncio.apply()

from menuflow.nodes import Base, convert_to_bool


def test_convert_to_bool():
    """It converts all values in a dictionary to booleans if they are strings that are equal
    to `True`, `true`, `false`, `False`
    """
    data = {"foo": "True", "bar": "False", "FooBar": "false", "BarFoo": "true", "BadFoo": "truee"}

    print(convert_to_bool(data))

    assert {
        "foo": True,
        "bar": False,
        "FooBar": False,
        "BarFoo": True,
        "BadFoo": "truee",
    } == convert_to_bool(data)


class TestBase:
    def test_render_data(self, base: Base):
        """It takes a string, list, or dictionary and replaces any string that matches a key in
        the `base.data` dictionary with the value of that key
        """
        assert "https://catfact.ninja/fact" == base.render_data("{{cat_fatc_url}}")
        assert ["https://catfact.ninja/fact", "", "Foo"] == base.render_data(
            ["{{cat_fatc_url}}", "{{foo}}", "Foo"]
        )
        assert {
            "foo": "https://catfact.ninja/fact",
            "https://catfact.ninja/fact": "foo",
            "bar": "",
        } == base.render_data(
            {"foo": "{{cat_fatc_url}}", "{{cat_fatc_url}}": "foo", "bar": "{{foo}}"}
        )
