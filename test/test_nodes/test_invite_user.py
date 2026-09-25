import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from menuflow.db.route import RouteState
from menuflow.menu import MenuClient
from menuflow.nodes.invite_user import InviteCase, InviteUser
from menuflow.room_sync_primitives import PrimitiveType, RoomSyncPrimitives

INVITEE = "@agent:example.com"
MENUBOT_MXID = "@menubot:example.com"


@pytest.fixture(autouse=True)
def clear_room_sync_primitives():
    RoomSyncPrimitives.room_sync_primitives.clear()
    yield
    RoomSyncPrimitives.room_sync_primitives.clear()


async def _wait_for_primitive(key, timeout: float = 1.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        primitive = RoomSyncPrimitives.room_sync_primitives.get(key)
        if primitive is not None:
            return primitive
        await asyncio.sleep(0.01)
    raise TimeoutError(f"Primitive {key} was not registered")


def _async_matrix_client(invite_user: InviteUser) -> None:
    client = invite_user.room.matrix_client
    client.invite_user = AsyncMock()
    client.kick_user = AsyncMock()
    client.leave_room = AsyncMock()
    client.handle_algorithm_completion = AsyncMock()


class TestInviteCase:
    def test_invite_case_values(self):
        assert InviteCase.ERROR.value == "error"
        assert InviteCase.JOIN.value == "join"
        assert InviteCase.REJECT.value == "reject"
        assert InviteCase.TIMEOUT.value == "timeout"


class TestInviteUserProperties:
    def test_on_join_default(self, invite_user: InviteUser):
        invite_user.content.pop("on_join")
        assert invite_user.on_join == "leave"

    @pytest.mark.asyncio
    async def test_invitee_render(self, invite_user: InviteUser):
        await invite_user.room.set_variable("route.agent_mxid", "@rendered:example.com")
        invite_user.content["invitee"] = "{{ route.agent_mxid }}"
        assert invite_user.invitee == "@rendered:example.com"

    def test_is_menubot_invitee_false(self, invite_user: InviteUser, mocker):
        mocker.patch.object(MenuClient, "cache", {})
        assert invite_user._is_menubot_invitee is False

    def test_is_menubot_invitee_true(self, invite_user: InviteUser, mocker):
        mocker.patch.object(MenuClient, "cache", {INVITEE: object()})
        assert invite_user._is_menubot_invitee is True


class TestRouteCase:
    @pytest.mark.asyncio
    async def test_route_case_join(self, invite_user: InviteUser):
        invite_user.room.update_menu = AsyncMock()
        await invite_user._route_case(InviteCase.JOIN)
        invite_user.room.update_menu.assert_awaited_once_with("next-node")

    @pytest.mark.asyncio
    async def test_route_case_reject(self, invite_user: InviteUser):
        invite_user.room.update_menu = AsyncMock()
        await invite_user._route_case(InviteCase.REJECT)
        invite_user.room.update_menu.assert_awaited_once_with("reject-node")

    @pytest.mark.asyncio
    async def test_route_case_timeout(self, invite_user: InviteUser):
        invite_user.room.update_menu = AsyncMock()
        await invite_user._route_case(InviteCase.TIMEOUT)
        invite_user.room.update_menu.assert_awaited_once_with("timeout-node")

    @pytest.mark.asyncio
    async def test_route_case_fail(self, invite_user: InviteUser):
        invite_user.room.update_menu = AsyncMock()
        await invite_user._route_case(InviteCase.ERROR)
        invite_user.room.update_menu.assert_awaited_once_with("fail-node")


class TestInviteAndWait:
    @pytest.mark.asyncio
    async def test_fail_when_invite_raises(self, invite_user: InviteUser):
        invite_user.room.matrix_client.invite_user = AsyncMock(side_effect=Exception("api down"))
        invite_ack = asyncio.get_running_loop().create_future()

        result = await invite_user._invite_and_wait(
            invite_user.room.room_id, INVITEE, 1.0, invite_ack
        )

        assert result == InviteCase.ERROR

    @pytest.mark.asyncio
    async def test_join_when_future_resolves_join(self, invite_user: InviteUser):
        invite_user.room.matrix_client.invite_user = AsyncMock()
        invite_ack = asyncio.get_running_loop().create_future()
        invite_ack.set_result(InviteCase.JOIN)

        result = await invite_user._invite_and_wait(
            invite_user.room.room_id, INVITEE, 1.0, invite_ack
        )

        assert result == InviteCase.JOIN

    @pytest.mark.asyncio
    async def test_reject_when_future_resolves_reject(self, invite_user: InviteUser):
        invite_user.room.matrix_client.invite_user = AsyncMock()
        invite_ack = asyncio.get_running_loop().create_future()
        invite_ack.set_result(InviteCase.REJECT)

        result = await invite_user._invite_and_wait(
            invite_user.room.room_id, INVITEE, 1.0, invite_ack
        )

        assert result == InviteCase.REJECT

    @pytest.mark.asyncio
    async def test_timeout_kicks_user(self, invite_user: InviteUser):
        invite_user.room.matrix_client.invite_user = AsyncMock()
        invite_user.room.matrix_client.kick_user = AsyncMock()
        invite_ack = asyncio.get_running_loop().create_future()

        result = await invite_user._invite_and_wait(
            invite_user.room.room_id, INVITEE, 0.01, invite_ack
        )

        assert result == InviteCase.TIMEOUT
        invite_user.room.matrix_client.kick_user.assert_awaited_once_with(
            invite_user.room.room_id, INVITEE
        )

    @pytest.mark.asyncio
    async def test_timeout_kick_failure_logged(self, invite_user: InviteUser, caplog):
        invite_user.room.matrix_client.invite_user = AsyncMock()
        invite_user.room.matrix_client.kick_user = AsyncMock(side_effect=Exception("kick failed"))
        invite_ack = asyncio.get_running_loop().create_future()

        with caplog.at_level(logging.ERROR):
            result = await invite_user._invite_and_wait(
                invite_user.room.room_id, INVITEE, 0.01, invite_ack
            )

        assert result == InviteCase.TIMEOUT
        assert "Failed to kick" in caplog.text


class TestEnsureJoin:
    @pytest.mark.asyncio
    async def test_ensure_join_returns_true_on_join(self, invite_user: InviteUser, mocker):
        mocker.patch.object(
            invite_user, "_invite_and_wait", AsyncMock(return_value=InviteCase.JOIN)
        )
        route_case = mocker.patch.object(invite_user, "_route_case", AsyncMock())

        joined = await invite_user._ensure_join(invite_user.room.room_id, INVITEE, 1.0, object())

        assert joined is True
        route_case.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ensure_join_returns_false_on_reject(self, invite_user: InviteUser, mocker):
        mocker.patch.object(
            invite_user, "_invite_and_wait", AsyncMock(return_value=InviteCase.REJECT)
        )
        route_case = mocker.patch.object(invite_user, "_route_case", AsyncMock())

        joined = await invite_user._ensure_join(invite_user.room.room_id, INVITEE, 1.0, object())

        assert joined is False
        route_case.assert_awaited_once_with(InviteCase.REJECT)

    @pytest.mark.asyncio
    async def test_ensure_join_returns_false_on_timeout(self, invite_user: InviteUser, mocker):
        mocker.patch.object(
            invite_user, "_invite_and_wait", AsyncMock(return_value=InviteCase.TIMEOUT)
        )
        route_case = mocker.patch.object(invite_user, "_route_case", AsyncMock())

        joined = await invite_user._ensure_join(invite_user.room.room_id, INVITEE, 1.0, object())

        assert joined is False
        route_case.assert_awaited_once_with(InviteCase.TIMEOUT)


class TestRunLeaveMode:
    @pytest.mark.asyncio
    async def test_run_join_and_leave_success(self, invite_user: InviteUser):
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.JOIN)
            leave_done = await _wait_for_primitive((room_id, PrimitiveType.LEAVE_DONE))
            leave_done.set()

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result == RouteState.INVITE
        invite_user.room.matrix_client.leave_room.assert_awaited_once()
        invite_user.room.update_menu.assert_awaited_once_with(node_id=None, state=RouteState.END)
        invite_user.room.matrix_client.handle_algorithm_completion.assert_awaited_once_with(
            room=invite_user.room, node=invite_user, evt=None
        )

    @pytest.mark.asyncio
    async def test_run_reject_returns_none(self, invite_user: InviteUser):
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.REJECT)

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result is None
        invite_user.room.update_menu.assert_awaited_once_with("reject-node")
        invite_user.room.matrix_client.leave_room.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_invite_timeout_returns_none(self, invite_user: InviteUser):
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        invite_user.content["timeout"] = 0.01

        result = await asyncio.wait_for(invite_user.run(), timeout=2)

        assert result is None
        invite_user.room.matrix_client.kick_user.assert_awaited_once()
        invite_user.room.update_menu.assert_awaited_once_with("timeout-node")

    @pytest.mark.asyncio
    async def test_run_leave_room_exception_returns_none(self, invite_user: InviteUser):
        _async_matrix_client(invite_user)
        invite_user.room.matrix_client.leave_room = AsyncMock(
            side_effect=Exception("leave failed")
        )
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.JOIN)

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result is None
        invite_user.room.update_menu.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_leave_done_timeout(self, invite_user: InviteUser):
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        invite_user.content["timeout"] = 0.01
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.JOIN)

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result is None
        invite_user.room.update_menu.assert_awaited_once_with("timeout-node")
        invite_user.room.matrix_client.handle_algorithm_completion.assert_not_awaited()


class TestRunNextNodeMode:
    @pytest.mark.asyncio
    async def test_run_next_node_join(self, invite_user: InviteUser, mocker):
        mocker.patch.object(MenuClient, "cache", {})
        invite_user.content["on_join"] = "next_node"
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.JOIN)

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result is None
        invite_user.room.update_menu.assert_awaited_once_with("next-node")
        invite_user.room.matrix_client.leave_room.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_next_node_reject(self, invite_user: InviteUser, mocker):
        mocker.patch.object(MenuClient, "cache", {})
        invite_user.content["on_join"] = "next_node"
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, INVITEE))
            ack.set_result(InviteCase.REJECT)

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result is None
        invite_user.room.update_menu.assert_awaited_once_with("reject-node")
        invite_user.room.matrix_client.leave_room.assert_not_awaited()


class TestRunMenubotInvitee:
    @pytest.mark.asyncio
    async def test_run_leave_mode_menubot_invitee_leaves(self, invite_user: InviteUser, mocker):
        mocker.patch.object(MenuClient, "cache", {MENUBOT_MXID: object()})
        invite_user.content["invitee"] = MENUBOT_MXID
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, MENUBOT_MXID))
            ack.set_result(InviteCase.JOIN)
            leave_done = await _wait_for_primitive((room_id, PrimitiveType.LEAVE_DONE))
            leave_done.set()

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result == RouteState.INVITE
        invite_user.room.matrix_client.leave_room.assert_awaited_once()
        invite_user.room.update_menu.assert_awaited_once_with(node_id=None, state=RouteState.END)
        invite_user.room.matrix_client.handle_algorithm_completion.assert_awaited_once_with(
            room=invite_user.room, node=invite_user, evt=None
        )

    @pytest.mark.asyncio
    async def test_run_next_node_mode_menubot_invitee_leaves(
        self, invite_user: InviteUser, mocker
    ):
        mocker.patch.object(MenuClient, "cache", {MENUBOT_MXID: object()})
        invite_user.content["invitee"] = MENUBOT_MXID
        invite_user.content["on_join"] = "next_node"
        _async_matrix_client(invite_user)
        invite_user.room.update_menu = AsyncMock()
        room_id = invite_user.room.room_id

        async def drive():
            ack = await _wait_for_primitive((room_id, MENUBOT_MXID))
            ack.set_result(InviteCase.JOIN)
            leave_done = await _wait_for_primitive((room_id, PrimitiveType.LEAVE_DONE))
            leave_done.set()

        driver = asyncio.create_task(drive())
        result = await asyncio.wait_for(invite_user.run(), timeout=2)
        await driver

        assert result == RouteState.INVITE
        invite_user.room.matrix_client.leave_room.assert_awaited_once()
        invite_user.room.update_menu.assert_awaited_once_with(node_id=None, state=RouteState.END)
