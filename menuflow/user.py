from typing import List

from mautrix.types import UserID

from .menu import Variable


class User:
    user_id: UserID
    phone: str
    variables: List[Variable]
    menu_context: str
