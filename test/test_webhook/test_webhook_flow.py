import pytest

from menuflow.db.route import RouteState
from menuflow.events.event_types import MenuflowNodeEvents
from menuflow.webhook.webhook import Webhook as Subscription

from .conftest import ROOM_ID, event_types

pytestmark = pytest.mark.asyncio

EVENT = {"user_id": "S1", "status": "ok"}
OTHER_EVENT = {"user_id": "S2", "status": "ok"}


class TestRoomWaitsFirst:
    async def test_event_arrives_and_room_continues_by_webhook_case(self, story, memory, events):
        """The room is already waiting: the POST that matches wakes it up and continues by the webhook case."""
        node = await story.room()
        await story.room_waits(node)

        status, _message = await story.post(EVENT)

        assert status == 200
        assert story.queued_for(node.room) == EVENT
        assert memory.subscription(ROOM_ID) is None

        await node.run(EVENT)

        assert node.room.route.node_id == "on_webhook"
        assert node.room.route.variables["route"]["payload"] == EVENT
        assert MenuflowNodeEvents.NodeInputData in event_types(events)

    async def test_room_is_subscribed_with_rendered_filter(self, story, memory, events):
        """When entering, the subscription saves the already rendered filter and the state remains in waiting."""
        node = await story.room()

        await story.room_waits(node)

        assert memory.subscription(ROOM_ID)["filter"] == '.user_id == "S1"'
        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT
        assert event_types(events) == [MenuflowNodeEvents.NodeEntry]


class TestEventArrivesFirst:
    async def test_event_is_stored_when_no_room_is_waiting(self, story, memory):
        """If no one is waiting, the event is saved and the API responds 202."""
        status, _message = await story.post(EVENT)

        assert status == 202
        assert len(memory.queued_events) == 1
        assert memory.subscriptions == []

    async def test_room_entering_later_receives_stored_event(self, story, memory):
        """The room that enters later receives the saved event and is not subscribed."""
        await story.post(EVENT)
        node = await story.room()

        await story.enter(node)

        assert node.room.route.node_id == "on_webhook"
        assert node.room.route.variables["route"]["payload"] == EVENT
        assert memory.subscriptions == []
        assert len(memory.queued_events) == 1

    async def test_stored_event_for_other_session_is_ignored(self, story, memory):
        """A saved event from another session is not delivered: the room subscribes and waits."""
        await story.post(OTHER_EVENT)
        node = await story.room(session_id="S1")

        await story.enter(node)

        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT
        assert memory.subscription(ROOM_ID) is not None
        assert len(memory.queued_events) == 1


class TestFilterAndBroadcast:
    async def test_event_not_delivered_to_room_with_different_filter(self, story, memory):
        """The event of S2 does not enter the queue of S1, which is subscribed."""
        first = await story.room(room_id="!s1:example.com", session_id="S1")
        second = await story.room(room_id="!s2:example.com", session_id="S2")
        await story.room_waits(first)
        await story.room_waits(second)

        status, _message = await story.post(OTHER_EVENT)

        assert status == 200
        assert story.queued_for(first.room) is None
        assert story.queued_for(second.room) == OTHER_EVENT
        assert memory.subscription("!s1:example.com") is not None
        assert memory.subscription("!s2:example.com") is None

    async def test_event_delivered_to_every_matching_room(self, story, memory):
        """Two rooms with the same filter receive the same event."""
        first = await story.room(room_id="!s1:example.com", session_id="S1")
        second = await story.room(room_id="!s2:example.com", session_id="S1")
        await story.room_waits(first)
        await story.room_waits(second)

        status, _message = await story.post(EVENT)

        assert status == 200
        assert story.queued_for(first.room) == EVENT
        assert story.queued_for(second.room) == EVENT
        assert memory.subscriptions == []

    async def test_room_without_running_algorithm_keeps_event_for_next_message(
        self, story, memory
    ):
        """Without an active algorithm the event is saved; the next message delivers it."""
        node = await story.room()
        await story.enter(node)

        status, _message = await story.post(EVENT)

        assert status == 202
        assert memory.subscription(ROOM_ID) is not None
        assert len(memory.queued_events) == 1

        await story.user_writes(node, "hola")

        assert node.room.route.node_id == "on_webhook"
        assert memory.subscription(ROOM_ID) is None

    async def test_orphan_subscription_is_removed(self, story, memory):
        """If the room is no longer in a webhook node, its subscription is removed."""
        node = await story.room()
        await story.room_waits(node)
        memory.nodes[ROOM_ID] = type("OtherNode", (), {"type": "message"})()

        await story.post(EVENT)

        assert memory.subscription(ROOM_ID) is None
        assert story.queued_for(node.room) is None


class TestUserMessages:
    async def test_cancel_exits_by_cancel_case_and_unsubscribes(self, story, memory):
        """Writing cancel exits by that case and removes the subscription."""
        node = await story.room()
        await story.room_waits(node)

        await story.user_writes(node, "cancelar")

        assert node.room.route.node_id == "on_cancel"
        assert memory.subscription(ROOM_ID) is None

    async def test_invalid_text_keeps_waiting(self, story, memory, events):
        """A text without case alerts, stays in the node and does not repeat NodeEntry."""
        node = await story.room()
        await story.room_waits(node)

        await story.user_writes(node, "hola")

        node.send_message.assert_awaited_once()
        assert node.send_message.await_args.args[1].body == "Opcion invalida"
        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT
        assert memory.subscription(ROOM_ID) is not None
        assert event_types(events).count(MenuflowNodeEvents.NodeEntry) == 1

    async def test_typing_webhook_does_not_trigger_webhook_case(self, story):
        """The word webhook written by the user does not trigger the HTTP event case."""
        node = await story.room()
        await story.room_waits(node)

        await story.user_writes(node, "webhook")

        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT


class TestTimeout:
    async def test_timeout_exits_by_timeout_case_and_unsubscribes(self, story, memory, events):
        """When the timeout expires the room exits by timeout and the subscription is removed."""
        node = await story.room()
        await story.room_waits(node)
        node.room.route.state = RouteState.TIMEOUT

        await node.run(None)

        assert node.room.route.node_id == "on_timeout"
        assert memory.subscription(ROOM_ID) is None
        assert MenuflowNodeEvents.NodeInputTimeout in event_types(events)

    async def test_timeout_wins_over_stored_event(self, story, memory):
        """A saved event does not win: the timeout still exits by its case."""
        node = await story.room()
        await story.enter(node)
        await story.post(EVENT)
        node.room.route.state = RouteState.TIMEOUT

        await node.run(None)

        assert node.room.route.node_id == "on_timeout"
        assert memory.subscription(ROOM_ID) is None


class TestSubscriptionCache:
    async def test_replaced_filter_is_not_removed_by_stale_subscription(self, story, memory):
        """Removing the old subscription does not remove the new one neither from the cache nor from the table."""
        node = await story.room(session_id="S1")
        await story.enter(node)
        stale = Subscription.by_room_id[ROOM_ID]

        await node.room.set_variable("route.session_id", "S2")
        node.room.route.state = RouteState.START
        await node.run(None)
        await stale.remove()

        current = memory.subscription(ROOM_ID)
        assert current is not None
        assert current["filter"] == '.user_id == "S2"'
        assert Subscription.by_room_id[ROOM_ID].filter == current["filter"]
