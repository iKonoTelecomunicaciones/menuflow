import nest_asyncio
import pytest

from menuflow.utils.flags import RenderFlags

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


def scope_variables() -> dict:
    """It returns a dictionary of scope variables for tests"""
    return {
        "route.customer_room_id": "!1234567890:example.com",
        "route.string_number": "123456789",
        "route.number": 61481488798,
        "route.dictionary": {"key": "value"},
        "route.code": "0030",
        "route.empty": None,
        "route.empty_str": "None",
        "route.height": 1.8,
        "route.balance": "1000.00",
        "route.bool": False,
        "route.bool_str": "false",
        "route.milliseconds": 0.02,
        "route.list": ["Luffy", "1", 2, 0.77, True],
    }


class TestBase:
    @pytest.mark.asyncio
    async def test_render_data_string(self, base: Base):
        """It takes a string with jinja variables and renders it"""

        scope_vars = scope_variables()
        await base.room.set_variables(scope_vars)
        await base.room.set_variables({"msg": "Hello\nWorld"})

        assert "Hello\nWorld" == base.render_data("{{ route.msg }}")

        # Simple strings
        assert "🙂" == base.render_data("\U0001f642")
        assert "<Hello, World>" == base.render_data("<Hello, World>")
        assert "“Hello World”" == base.render_data("“Hello World”") # fmt: skip
        assert "Hello \"World" == base.render_data("Hello \"World") # fmt: skip
        assert "Hello \\\"World" == base.render_data("Hello \\\"World") # fmt: skip
        assert "Hello \rWorld" == base.render_data("Hello \rWorld")
        assert "Hello \nWorld" == base.render_data("Hello \nWorld")

        # Jinja variables
        assert "https://catfact.ninja/fact" == base.render_data("{{ flow.cat_fatc_url }}")
        assert "0030" == base.render_data("{{ route.code }}")
        assert "1000.00" == base.render_data("{{ route.balance }}")
        assert "10 " == base.render_data("{{ flow.counter }} ")
        assert "010" == base.render_data("0{{ flow.counter }}")
        assert " 10" == base.render_data(" {{ flow.counter }}")
        assert base.render_data("{{ flow.bool }}") is True
        assert base.render_data("{{ flow.bool_str }}") is True
        assert "https://catfact.ninja/fact/87684525412/61481488798" == base.render_data(
            "{{ flow.cat_fatc_url }}/{{ flow.number }}/{{ flow.str_number }}"
        )
        assert "line 1\nline 2\nline 3" == base.render_data("{{ flow.multiple_lines }}")

    @pytest.mark.asyncio
    async def test_render_data_dict(self, base: Base):
        """It takes a dictionary and renders it"""

        scope_vars = scope_variables()
        await base.room.set_variables(scope_vars)

        # Simple dictionaries
        assert {"key": "value"} == base.render_data("{\n  \"key\": \"value\"\n}") # fmt: skip
        assert {"key": "value ñ"} == base.render_data("{\n  \"key\": \"value ñ\"\n}") # fmt: skip
        assert {"key": "🙂"} == base.render_data("{\n  \"key\": \"🙂\"\n}") # fmt: skip
        assert {"emoji": "🙂"} == base.render_data("{\n  \"emoji\": \"\U0001f642\"\n}") # fmt: skip
        assert {"key": "value\nData"} == base.render_data("{\n  \"key\": \"value\\nData\"\n}") # fmt: skip
        assert {"key": "value"} == base.render_data("{'key': 'value'}")

        # Jinja variables
        assert {"key": "value"} == base.render_data("{{ flow.dictionary }}")
        assert {"number": "{{ flow.number }"} == base.render_data({"number": "{{ flow.number }"})
        assert {"foo": "https://catfact.ninja/fact", "bar": ""} == base.render_data(
            {"foo": "{{ flow.cat_fatc_url }}", "bar": "{{ foo }}"}
        )

    @pytest.mark.asyncio
    async def test_render_data_list(self, base: Base):
        scope_vars = scope_variables()
        await base.room.set_variables(scope_vars)

        # Simple lists
        assert ["admin", "user"] == base.render_data("[\"admin\", \"user\"]") # fmt: skip
        assert [True, False] == base.render_data("[True, False]")

        # Jinja variables
        assert ["Luffy", "1", 2, 0.77, True] == base.render_data("{{ route.list }}")
        assert ["https://catfact.ninja/fact", "", "Foo"] == base.render_data(
            ["{{ flow.cat_fatc_url }}", "{{ foo }}", "Foo"]
        )

    @pytest.mark.asyncio
    async def test_render_data_bool_none(self, base: Base):
        scope_vars = scope_variables()
        await base.room.set_variables(scope_vars)

        # Simple strings
        assert base.render_data("None") is None
        assert base.render_data("none") is None

        assert base.render_data("True") is True
        assert base.render_data("true") is True
        assert base.render_data("False") is False
        assert base.render_data("false") is False

        # Jinja variables
        assert base.render_data("{{ route.bool }}") is False
        assert base.render_data("{{ route.bool_str }}") is False
        assert base.render_data("{{ '1' | bool }}") is True
        assert base.render_data("{{ flow.bool }}") is True
        assert base.render_data("{{ flow.bool | bool }}") is True
        assert base.render_data("{{ flow.bool_str }}") is True

        assert base.render_data("{{ route.empty }}") is None
        assert base.render_data("{{ route.empty_str }}") is None
        assert base.render_data("{{ flow.none_str }}") is None
        assert base.render_data("{{ flow.none }}") is None

    @pytest.mark.asyncio
    async def test_render_data_numeric(self, base: Base):
        scope_vars = scope_variables()
        await base.room.set_variables(scope_vars)

        # Simple strings
        assert 1 == base.render_data("1")
        assert 1.0 == base.render_data("1.0")

        # Jinja variables
        assert 1.8 == base.render_data("{{ route.height }}")
        assert 0.02 == base.render_data("{{ route.milliseconds }}")
        assert 10 == base.render_data("{{ flow.counter }}")
        assert 61481488798 == base.render_data("{{ flow.str_number }}")

        assert "61481488798" == base.render_data("'{{ flow.str_number }}'")

    @pytest.mark.asyncio
    async def test_render_data_stringify(self, base: Base):
        assert {"key": "line 1\nline 2\nline 3"} == base.render_data(
            "{\n  \"key\": \"{{ flow.multiple_lines }}\"}",
            flags=RenderFlags.CUSTOM_ESCAPE | RenderFlags.LITERAL_EVAL
        ) # fmt: skip

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
            "flow_variables": {
                "cat_fatc_url": "https://catfact.ninja/fact",
                "cat_name": "Luffy",
                "str_number": "61481488798",
                "number": 87684525412,
                "counter": 10,
                "dictionary": {"key": "value"},
                "bool": True,
                "bool_str": "true",
                "none_str": "None",
                "none": None,
                "multiple_lines": "line 1\nline 2\nline 3",
            },
        } == base.render_data(
            """
{
    "Cat_name": "{{ flow.cat_name }}",
    "Foo": ["bar", "foo"],
    "flow_variables": {{ flow }},
}""",
            flags=RenderFlags.CUSTOM_ESCAPE | RenderFlags.LITERAL_EVAL,
        )

        assert {
            "Cat_name": "Luffy",
            "Foo": ["bar", "foo"],
            "multiple_lines": "line 1\nline 2\nline 3",
        } == base.render_data(
            """
{
    "Cat_name": "{{ flow.cat_name }}",
    "Foo": ["bar", "foo"],
    "multiple_lines": "{{ flow.multiple_lines }}"
}""",
            flags=RenderFlags.CUSTOM_ESCAPE | RenderFlags.LITERAL_EVAL,
        )

    @pytest.mark.asyncio
    async def test_save_complex_data(self, base: Base):
        """
        It test if a route variable can save a complex data structure
        It checks if the method can handle nested lists and dictionaries,
        and if it correctly replaces the placeholders with the corresponding values.
        It also checks if the method can handle a dictionary with a list as a value.
        """
        scope_vars = scope_variables()
        data = {
            "Cat_name": "{{ flow.cat_name }}",
            "Foo": ["bar", "foo"],
            "number": "{{ route.number }}",
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

        test_data = await self.config_variables(base, scope_vars, data)

        assert test_data.get("accounts")[0].get("rooms")[0] == base.render_data(
            "{{ route.customer_room_id }}"
        )
        assert f'{scope_vars.get("route.number")}' == test_data.get("number")

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

    @pytest.mark.asyncio
    async def test_render_data_body_str(self, base: Base):
        """
        It test if a route variable can save a body as a string
        and if it correctly replaces the placeholders with the corresponding values.
        """
        scope_vars = {
            "age": 30,
            "roles": ["admin", "user"],
            "roles_str": "[\"admin\", \"user\"]", # fmt: skip
            "active": True,
            "name": "\n \ud83d\ude42\u00d1\u00f1John Doe",
            "address": {
                "street": "\t123 Main St",
                "data": '🙂 Hello\n"letter ñ"\\',
                "city": "Anytown",
                "zip_code": "12345",
            },
        }

        data = """{\n  \"name\": \"{{ route.name }}\",\n  \"age\": {{ route.age }},\n  \"active\": {{ route.active }},\n\n  \"roles\": [\n    {% for rol in route.roles %}\n\"{{ rol }}\"{% if not loop.last %},{% endif %}\n    {% endfor %}\n  ],\n\n  \"address\": {\n    \"street\": \"{{ route.address.street }}\",\n    \"data\": \"🙂 Hello\\n\\\"letter ñ\\\"\\\\\",\n    \"city\": \"{{ route.address.city }}\",\n    \"zip_code\": \"{{ route.address.zip_code }}\"\n  },\n  \"flow_name\" : \"{{ flow.name }}\"\n}"""

        test_data = await self.config_variables(
            base, scope_vars, data, flags=RenderFlags.CUSTOM_ESCAPE | RenderFlags.LITERAL_EVAL
        )

        assert "\n 🙂ÑñJohn Doe" == test_data.get("name")
        assert scope_vars.get("age") == test_data.get("age")
        assert scope_vars.get("active") == test_data.get("active")
        assert scope_vars.get("roles") == test_data.get("roles")
        assert scope_vars.get("address") == test_data.get("address")
        assert '🙂 Hello\n"letter ñ"\\' == test_data.get("address").get("data")
        assert ["admin", "user"] == test_data.get("roles")
        assert "\t123 Main St" == test_data.get("address").get("street")
        assert "Anytown" == test_data.get("address").get("city")
        assert "12345" == test_data.get("address").get("zip_code")
        assert "" == test_data.get("flow_name")

    @pytest.mark.asyncio
    async def test_render_data_opt_in(self, base: Base):
        """
        It test if a route variable can save a opt_in as a string
        and if it correctly replaces the placeholders with the corresponding values.
        """
        scope_vars = {
            "route.customer_mxid": "@mxwa_573009091234:darknet",
            "route.account_type_id": 1,
            "route.account_type_id_str": "1",
        }

        opt_in_body = """{
  "accounts": [
    {
      "label": "Created by menuflow",
      "identifier": "{{ route.customer_mxid | user_bridge_account_id }}",
      "account_type_id": {{ route.account_type_id }},
      "account_type_id_str": "{{ route.account_type_id_str }}",
      "account_type_id_int": "{{ route.account_type_id }}"

    }
  ]
}"""

        test_data = await self.config_variables(
            base,
            scope_vars,
            opt_in_body,
            flags=RenderFlags.CUSTOM_ESCAPE | RenderFlags.LITERAL_EVAL,
        )

        # Verify that the test data is saved correctly
        assert "Created by menuflow" == test_data.get("accounts")[0].get("label")
        assert "573009091234" == test_data.get("accounts")[0].get("identifier")
        assert 1 == test_data.get("accounts")[0].get("account_type_id")
        assert "1" == test_data.get("accounts")[0].get("account_type_id_str")
        assert "1" == test_data.get("accounts")[0].get("account_type_id_int")

    @pytest.mark.asyncio
    async def config_variables(
        self,
        base: Base,
        scope_vars: dict,
        data: dict,
        flags: RenderFlags = RenderFlags.REMOVE_QUOTES
        | RenderFlags.LITERAL_EVAL
        | RenderFlags.CONVERT_TO_TYPE,
    ):
        # Set the scope variables
        await base.room.set_variables(scope_vars)

        # Render the data
        data_rendered = base.render_data(data, flags=flags)

        # Save the rendered data to the route variable
        await base.room.set_variable("test_data", data_rendered)

        # Get the test data in route variable
        return await base.room.get_variable("test_data")

    @pytest.mark.asyncio
    async def test_render_data_message_text(self, base: Base):
        scope_vars = {
            "route.name": "John",
            "route.lastname": "Doe",
            "route.input_test": "10: Option 10\n11: Option 11",
        }

        message_text = """
🚀 Hello {{ route.name }}, {{ route.lastname }}: 🚀

**1**: Hello 🏢
**2**: exit option
{{ route.input_test }}
"""

        test_data = await self.config_variables(base, scope_vars, message_text)

        assert (
            "\n🚀 Hello John, Doe: 🚀\n\n**1**: Hello 🏢\n**2**: exit option\n10: Option 10\n11: Option 11"
            == f"{test_data}"
        )
