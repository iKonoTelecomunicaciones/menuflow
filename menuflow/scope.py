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

    def _locals_frame(self, scope: str, use_locals: bool = True) -> dict | None:
        if not use_locals or scope != Scopes.ROUTE.value or not self.route:
            return None
        return self.route.current_frame

    def get(self, scope: Scopes | str, use_locals: bool = True) -> dict:
        s = self._key(scope)
        if frame := self._locals_frame(s, use_locals):
            return frame.setdefault("locals", {})
        return self._model(s)._variables.setdefault(s, {})

    def set(self, scope: Scopes | str, data: dict, use_locals: bool = True) -> None:
        s = self._key(scope)
        if frame := self._locals_frame(s, use_locals):
            frame["locals"] = data or {}
            return
        self._model(s)._variables[s] = data or {}

    def clear(self, scope: Scopes | str, use_locals: bool = True) -> None:
        self.set(self._key(scope), {}, use_locals=use_locals)

    async def update(self, scope: Scopes | str) -> None:
        await self._model(self._key(scope)).update_variables()
