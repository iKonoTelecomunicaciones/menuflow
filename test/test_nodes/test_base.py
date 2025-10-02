import nest_asyncio
import pytest

nest_asyncio.apply()

from menuflow.nodes import Base, convert_to_bool


def test_convert_to_bool():
    """It converts all values in a dictionary to booleans if they are strings that are equal
    to `True`, `true`, `false`, `False`
    """
    data = {"foo": "True", "bar": "False", "FooBar": "false", "BarFoo": "true", "BadFoo": "truee"}

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
        assert "https://catfact.ninja/fact" == base.render_data("{{ flow.cat_fatc_url }}")
        assert ["https://catfact.ninja/fact", "", "Foo"] == base.render_data(
            ["{{ flow.cat_fatc_url }}", "{{ foo }}", "Foo"]
        )
        assert {
            "foo": "https://catfact.ninja/fact",
            "bar": "",
        } == base.render_data(
            {
                "foo": "{{ flow.cat_fatc_url }}",
                "bar": "{{ foo }}",
            }
        )
        assert {"code": "0030"} == base.render_data({"code": "0030"})
        assert {"empty": None} == base.render_data({"empty": "None"})
        assert {"height": 1.8} == base.render_data({"height": 01.80})
        assert {"balance": "1000.00"} == base.render_data({"balance": "1000.00"})
        assert {"bool": False} == base.render_data({"bool": "false"})
        assert ["Luffy", 1, 0.77, True] == base.render_data(["Luffy", "1", 000.7700, "true"])

    def test_render_complex_data(self, base: Base):
        """
        Test rendering complex data structures in the render_data method.
        It checks if the method can handle nested lists and dictionaries,
        and if it correctly replaces the placeholders with the corresponding values.
        It also checks if the method can handle a dictionary with a list as a value.
        """
        assert [
            "https://catfact.ninja/fact",
            "Luffy",
            "Foo",
        ] == base.render_data(["{{ flow.cat_fatc_url }}", "{{ flow.cat_name }}", "Foo"])
        assert [
            {
                "Cat_name": "Luffy",
                "Foo": ["bar", "foo"],
            }
        ] == base.render_data(
            [
                {
                    "Cat_name": "{{ flow.cat_name }}",
                    "Foo": ["bar", "foo"],
                }
            ]
        )
        assert [
            [
                {
                    "Cat_name": "Luffy",
                    "Foo": ["bar", "foo"],
                }
            ]
        ] == base.render_data(
            [
                [
                    {
                        "Cat_name": "{{ flow.cat_name }}",
                        "Foo": ["bar", "foo"],
                    }
                ]
            ]
        )
        assert {
            "Cat_name": "Luffy",
            "Foo": ["bar", "foo"],
            "flow_variables": {"cat_fatc_url": "https://catfact.ninja/fact", "cat_name": "Luffy"},
        } == base.render_data(
            {
                "Cat_name": "{{ flow.cat_name }}",
                "Foo": ["bar", "foo"],
                "flow_variables": "{{ flow }}",
            }
        )

    @pytest.mark.asyncio
    async def test_save_complex_data(self, base: Base):
        """
        It test if a route variable can save a complex data structure
        It checks if the method can handle nested lists and dictionaries,
        and if it correctly replaces the placeholders with the corresponding values.
        It also checks if the method can handle a dictionary with a list as a value.
        """
        data = {
            "Cat_name": "{{ flow.cat_name }}",
            "Foo": ["bar", "foo"],
            "accounts": [
                {
                    "account_id": 1,
                    "identifier": "573207051244",
                    "account_type_id": 1,
                    "account_type_name": "Phone",
                    "label": "",
                    "deleted": False,
                    "rooms": ["{{ route.customer_room_id }}"],
                    "opt_in": None,
                }
            ],
        }

        data_rendered = base.render_data(data)

        # Save the rendered data to the route variable
        await base.room.set_variable("test_data", data_rendered)

        # Verify that the data is saved correctly
        assert await base.room.get_variable("test_data") == data_rendered

        # Get the data from the route variable
        test_data = await base.room.get_variable("test_data")
        customer_room_id = test_data.get("accounts")[0].get("rooms")[0]

        # Verify that the data is saved correctly
        assert customer_room_id == base.render_data("{{ route.customer_room_id }}")

    @pytest.mark.asyncio
    async def test_crud_variables(self, base: Base):
        """
        It test if the crud variables method can get the variables from the route variable
        """
        data = {
            # Basic
            "simple": "value1",
            "nested.level1": "value2",
            "nested2.level1.level2": "value3",
            # Config
            "config.logging.list": ["value4", {}, ["sub_value1", "sub_value2"]],
            "config.logging.list[1][0]": "sub_value0",
            "config.logging.list[1].a": "value6",
            "config.logging.list[1].b": "value7",
            "config.logging.list[1].c": ["value8", {"value9": "value10"}],
            "config.logging.list[1].c[0]": "value_test",
            "config.logging.list[1].c[1].value9": "value11",
            # Key5
            "key5[data].subkey1[0]": "value8",
            # Sections
            "sections['key-with-dash'].value": "dash",
            "sections['key.section.dot'].value": "dot",
            "sections['key with spaces'].value": "spaces",
            "sections['key_with_underscore'].value": "underscore",
            "sections['key:with:colon'].value": "colon",
            "sections['key$with$dollar'].value": "dollar",
            "sections['key@with@at'].value": "at",
            "sections['key#with#hash'].value": "hash",
            "sections['key&with&ampersand'].value": "ampersand",
            "sections['key*with*asterisk'].value": "asterisk",
            "sections['key+with+plus'].value": "plus",
            # Users
            "users['@main1:ABC'].name": "Alice",
            "users['@main1:ABC'].role": "admin",
            "users['@main1:ABC'].passwd": "alice_passwd",
            # Special
            "special['key\nnewline'].value": "newline",
            "special['key\r\nnewline'].value": "crlf",
            "special['key\rnewline'].value": "cr",
            "special['key\ttab'].value": "tab",
            "special['key\vvertical'].value": "vertical",
            "special['key\fformfeed'].value": "formfeed",
            "special['key\bbackspace'].value": "backspace",
            "special['key\aalert'].value": "alert",
        }

        # Save the data to the route variable
        await base.room.set_variables(data)

        # Get the data from the route variable
        # Example: simple
        assert await base.room.get_variable("simple") == "value1"

        # Example: nested
        expected = {"level1": "value2"}
        assert await base.room.get_variable("nested") == expected

        # Example: nested2
        expected = {"level1": {"level2": "value3"}}
        assert await base.room.get_variable("nested2") == expected

        # Example: config
        expected = {
            "logging": {
                "list": [
                    "value4",
                    {
                        "0": "sub_value0",
                        "a": "value6",
                        "b": "value7",
                        "c": ["value_test", {"value9": "value11"}],
                    },
                    ["sub_value1", "sub_value2"],
                ]
            }
        }
        assert await base.room.get_variable("config") == expected

        # Example: key5
        expected = {"data": {"subkey1": {"0": "value8"}}}
        assert await base.room.get_variable("key5") == expected

        # Example: sections
        expected = {
            "key-with-dash": {"value": "dash"},
            "key.section.dot": {"value": "dot"},
            "key with spaces": {"value": "spaces"},
            "key_with_underscore": {"value": "underscore"},
            "key:with:colon": {"value": "colon"},
            "key$with$dollar": {"value": "dollar"},
            "key@with@at": {"value": "at"},
            "key#with#hash": {"value": "hash"},
            "key&with&ampersand": {"value": "ampersand"},
            "key*with*asterisk": {"value": "asterisk"},
            "key+with+plus": {"value": "plus"},
        }
        assert await base.room.get_variable("sections") == expected

        # Example: users
        expected = {
            "@main1:ABC": {"name": "Alice", "role": "admin", "passwd": "alice_passwd"},
        }
        assert await base.room.get_variable("users") == expected

        # Example: special
        expected = {
            "key\nnewline": {"value": "newline"},
            "key\r\nnewline": {"value": "crlf"},
            "key\rnewline": {"value": "cr"},
            "key\ttab": {"value": "tab"},
            "key\vvertical": {"value": "vertical"},
            "key\fformfeed": {"value": "formfeed"},
            "key\bbackspace": {"value": "backspace"},
            "key\aalert": {"value": "alert"},
        }
        assert await base.room.get_variable("special") == expected

        # Delete the data from the route variable
        await base.room.del_variables(
            [
                "config.logging.list[1].c[0]",
                "config.logging.list[1].a",
                "users['@main1:ABC']",
                "key5[data].subkey1['0']",
            ]
        )

        # Verify that the data is deleted in config
        expected = {
            "logging": {
                "list": [
                    "value4",
                    {
                        "0": "sub_value0",
                        "b": "value7",
                        "c": [{"value9": "value11"}],
                    },
                    ["sub_value1", "sub_value2"],
                ]
            }
        }

        assert await base.room.get_variable("config") == expected

        # Verify that the data is deleted in key5
        assert await base.room.get_variable("key5") == {"data": {"subkey1": {}}}

        # Verify that the data is deleted in users
        assert await base.room.get_variable("users") == {}
