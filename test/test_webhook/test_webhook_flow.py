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
        """La sala ya espera: el POST que coincide la despierta y sigue por el case webhook."""
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
        """Al entrar, la suscripción guarda el filtro ya renderizado y el estado queda en espera."""
        node = await story.room()

        await story.room_waits(node)

        assert memory.subscription(ROOM_ID)["filter"] == '.user_id == "S1"'
        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT
        assert event_types(events) == [MenuflowNodeEvents.NodeEntry]


class TestEventArrivesFirst:
    async def test_event_is_stored_when_no_room_is_waiting(self, story, memory):
        """Si nadie espera, el evento se guarda y la API responde 202."""
        status, _message = await story.post(EVENT)

        assert status == 202
        assert len(memory.queued_events) == 1
        assert memory.subscriptions == []

    async def test_room_entering_later_receives_stored_event(self, story, memory):
        """La sala que entra después recibe el evento guardado y no queda suscrita."""
        await story.post(EVENT)
        node = await story.room()

        await story.enter(node)

        assert node.room.route.node_id == "on_webhook"
        assert node.room.route.variables["route"]["payload"] == EVENT
        assert memory.subscriptions == []
        assert len(memory.queued_events) == 1

    async def test_stored_event_for_other_session_is_ignored(self, story, memory):
        """Un evento guardado de otra sesión no se entrega: la sala se suscribe y espera."""
        await story.post(OTHER_EVENT)
        node = await story.room(session_id="S1")

        await story.enter(node)

        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT
        assert memory.subscription(ROOM_ID) is not None
        assert len(memory.queued_events) == 1


class TestFilterAndBroadcast:
    async def test_event_not_delivered_to_room_with_different_filter(self, story, memory):
        """El evento de S2 no entra en la cola de S1, que sigue suscrita."""
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
        """Dos salas con el mismo filtro reciben el mismo evento."""
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
        """Sin algoritmo activo el evento se guarda; el siguiente mensaje lo entrega."""
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
        """Si la sala ya no está en un nodo webhook, su suscripción se elimina."""
        node = await story.room()
        await story.room_waits(node)
        memory.nodes[ROOM_ID] = type("OtherNode", (), {"type": "message"})()

        await story.post(EVENT)

        assert memory.subscription(ROOM_ID) is None
        assert story.queued_for(node.room) is None


class TestUserMessages:
    async def test_cancel_exits_by_cancel_case_and_unsubscribes(self, story, memory):
        """Escribir cancelar sale por ese case y borra la suscripción."""
        node = await story.room()
        await story.room_waits(node)

        await story.user_writes(node, "cancelar")

        assert node.room.route.node_id == "on_cancel"
        assert memory.subscription(ROOM_ID) is None

    async def test_invalid_text_keeps_waiting(self, story, memory, events):
        """Un texto sin case avisa, sigue en el nodo y no repite NodeEntry."""
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
        """La palabra webhook escrita por el usuario no dispara el case del evento HTTP."""
        node = await story.room()
        await story.room_waits(node)

        await story.user_writes(node, "webhook")

        assert node.room.route.node_id == "webhook_0"
        assert node.room.route.state == RouteState.INPUT


class TestTimeout:
    async def test_timeout_exits_by_timeout_case_and_unsubscribes(self, story, memory, events):
        """Al vencer la espera la sala sale por timeout y se borra la suscripción."""
        node = await story.room()
        await story.room_waits(node)
        node.room.route.state = RouteState.TIMEOUT

        await node.run(None)

        assert node.room.route.node_id == "on_timeout"
        assert memory.subscription(ROOM_ID) is None
        assert MenuflowNodeEvents.NodeInputTimeout in event_types(events)

    async def test_timeout_wins_over_stored_event(self, story, memory):
        """Un evento guardado no gana: el timeout sigue saliendo por su case."""
        node = await story.room()
        await story.enter(node)
        await story.post(EVENT)
        node.room.route.state = RouteState.TIMEOUT

        await node.run(None)

        assert node.room.route.node_id == "on_timeout"
        assert memory.subscription(ROOM_ID) is None


class TestSubscriptionCache:
    async def test_replaced_filter_is_not_removed_by_stale_subscription(self, story, memory):
        """Borrar la suscripción vieja no quita la nueva ni de la caché ni de la tabla."""
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
