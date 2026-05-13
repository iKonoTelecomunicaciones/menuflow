import json

from .db.room import Room
from .db.route import Route
from .utils.types import Scopes


class Scope:
    def __init__(self, room: Room):
        self.room: Room = room

    @property
    def route(self) -> Route:
        return self.room.route

    def _key(self, scope: Scopes | str) -> str:
        return scope.value if isinstance(scope, Scopes) else scope

    def _model(self, scope: str):
        s = self._key(scope)
        return self.route if s in (Scopes.ROUTE.value, Scopes.NODE.value) else self.room

    def get(self, scope: Scopes | str) -> dict:
        if scope == Scopes.EXTERNAL.value or scope == Scopes.EXTERNAL:
            return self.route._external_vars
        s = self._key(scope)
        return self._model(s)._variables.setdefault(s, {})

    def set(self, scope: Scopes | str, data: dict) -> None:
        if scope == Scopes.EXTERNAL.value or scope == Scopes.EXTERNAL:
            self.route.external_vars = json.dumps(data or {})
            return
        s = self._key(scope)
        self._model(s)._variables[s] = data or {}

    def clear(self, scope: Scopes | str) -> None:
        self.set(scope, {})

    async def persist(self, scope: Scopes | str) -> None:
        if scope == Scopes.EXTERNAL.value or scope == Scopes.EXTERNAL:
            await self.route.update_external_vars()
            return
        await self._model(scope).update_variables()
