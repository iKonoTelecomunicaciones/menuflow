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
        s = self._key(scope)
        await self._model(s).update_variables()

        if s not in self.ROUTE_SCOPES:
            sync = getattr(self.room, "sync_room_vars_cache", None)
            if sync and self.room.room_id:
                sync(
                    room_id=self.room.room_id,
                    variables=self.room.variables,
                    bot_mxid=getattr(self.room, "bot_mxid", None),
                )
