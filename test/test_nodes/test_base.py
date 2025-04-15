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
            "https://catfact.ninja/fact": "foo",
            "bar": "",
        } == base.render_data(
            {
                "foo": "{{ flow.cat_fatc_url }}",
                "{{ flow.cat_fatc_url }}": "foo",
                "bar": "{{ foo }}",
            }
        )

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
                "https://catfact.ninja/fact": "foo",
                "Cat_name": "Luffy",
                "Foo": ["bar", "foo"],
            }
        ] == base.render_data(
            [
                {
                    "{{ flow.cat_fatc_url }}": "foo",
                    "Cat_name": "{{ flow.cat_name }}",
                    "Foo": ["bar", "foo"],
                }
            ]
        )
        assert [
            [
                {
                    "https://catfact.ninja/fact": "foo",
                    "Cat_name": "Luffy",
                    "Foo": ["bar", "foo"],
                }
            ]
        ] == base.render_data(
            [
                [
                    {
                        "{{ flow.cat_fatc_url }}": "foo",
                        "Cat_name": "{{ flow.cat_name }}",
                        "Foo": ["bar", "foo"],
                    }
                ]
            ]
        )
        assert {
            "https://catfact.ninja/fact": "foo",
            "Cat_name": "Luffy",
            "Foo": ["bar", "foo"],
            "flow_variables": {"cat_fatc_url": "https://catfact.ninja/fact", "cat_name": "Luffy"},
        } == base.render_data(
            {
                "{{ flow.cat_fatc_url }}": "foo",
                "Cat_name": "{{ flow.cat_name }}",
                "Foo": ["bar", "foo"],
                "flow_variables": "{{ flow }}",
            }
        )

    @pytest.mark.asyncio
    async def test_save_comloex_data(self, base: Base):
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
        assert customer_room_id ==  base.render_data("{{ route.customer_room_id }}")
