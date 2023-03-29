import nest_asyncio
import pytest
from asyncmock import AsyncMock
from mautrix.client import Client
from pytest_mock import MockerFixture

from menuflow.nodes import Location

nest_asyncio.apply()


class TestLocationNode:
    def test_longitude_latitude(self, location: Location):
        assert location.latitude == 132.4877572355567
        assert location.longitude == 33.73677405847739

    @pytest.mark.asyncio
    async def test_run(self, location: Location, mocker: MockerFixture):
        async_mock = AsyncMock()
        mock_func = mocker.patch.object(Client, "send_message", side_effect=async_mock)
        await location.run()
        assert mock_func.called == True
