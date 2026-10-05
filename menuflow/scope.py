from .db.room import Room
from .db.route import Route
from .utils.types import Scopes


class Scope:
    ROUTE_SCOPES = (Scopes.ROUTE.value, Scopes.NODE.value)

    def __init__(self, room: Room):
        self.room: Room = room

    @property
    def route(self) -> Route:
        return self.room.route

    def _key(self, scope: Scopes | str) -> str:
        return scope.value if isinstance(scope, Scopes) else scope

    def _model(self, scope: str):
        return self.route if scope in self.ROUTE_SCOPES else self.room

    def get(self, scope: Scopes | str) -> dict:
        s = self._key(scope)
        return self._model(s)._variables.setdefault(s, {})

    def set(self, scope: Scopes | str, data: dict) -> None:
        s = self._key(scope)
        self._model(s)._variables[s] = data or {}

    def clear(self, scope: Scopes | str) -> None:
        self.set(self._key(scope), {})

    async def update(self, scope: Scopes | str) -> None:
        await self._model(self._key(scope)).update_variables()
