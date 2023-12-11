import nest_asyncio
import pytest

from menuflow.nodes import Switch

nest_asyncio.apply()


class TestSwitchNode:
    @pytest.mark.asyncio
    async def test_validation(self, switch: Switch):
        """It sets the `cat_age` variable to 5, then checks that the `validation`
        variable is set to `ok`, then sets the `cat_age` variable to 12,
        then checks that the `validation` variable is set to `ko`
        """
        await switch.room.set_variable("cat_age", "5")
        assert switch.validation == "ok"
        await switch.room.set_variable("cat_age", "12")
        assert switch.validation == "ko"

    def test_cases(self, switch: Switch):
        assert switch.cases == [
            {
                "id": "ok",
                "o_connection": "request-1",
                "variables": {"cat_message": "Your cat is a puppy"},
            },
            {
                "id": "ko",
                "o_connection": "request-1",
                "variables": {"cat_message": "Your cat is an adult"},
            },
        ]

    @pytest.mark.asyncio
    async def test_load_cases(self, switch: Switch):
        assert await switch.load_cases() == {
            "ok": {
                "o_connection": "request-1",
                "variables": {"cat_message": "Your cat is a puppy"},
            },
            "ko": {
                "o_connection": "request-1",
                "variables": {"cat_message": "Your cat is an adult"},
            },
        }

    @pytest.mark.asyncio
    async def test__run(self, switch: Switch):
        await switch.room.set_variable("cat_age", "5")
        assert await switch._run() == "request-1"
        await switch.room.set_variable("cat_age", "12")
        assert await switch._run() == "request-1"

    @pytest.mark.asyncio
    async def test_run(self, switch: Switch):
        await switch.room.set_variable("cat_age", "5")
        await switch.run()
        assert switch.room.route.node_id == "request-1"
        await switch.room.set_variable("cat_age", "12")
        await switch.run()
        assert switch.room.route.node_id == "request-1"

    @pytest.mark.asyncio
    async def test_get_case_by_id(self, switch: Switch):
        assert await switch.get_case_by_id("ok") == "request-1"
        assert await switch.get_case_by_id("ko") == "request-1"
