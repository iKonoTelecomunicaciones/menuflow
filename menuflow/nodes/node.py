from __future__ import annotations

from json import JSONDecodeError, dumps, loads
from typing import Any, Dict, List

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..jinja.jinja_template import jinja_env
from ..user import User
from ..utils.base_logger import BaseLogger


@dataclass
class Node(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    type: str = ib(metadata={"json": "type"})
    user: User

    def build_node(self):
        return self.deserialize(self.__dict__)

    def render_data(self, data: Dict | List | str) -> Dict | List | str:
        """It takes a dictionary or list, converts it to a string,
        and then uses Jinja to render the string

        Parameters
        ----------
        data : Dict | List
            The data to be rendered.

        Returns
        -------
            A dictionary or list.

        """

        if isinstance(data, str):
            data_template = jinja_env.from_string(data)
        else:
            try:
                data_template = jinja_env.from_string(dumps(data))
            except Exception as e:
                self.log.exception(e)
                return

        try:
            return loads(data_template.render(**self.user._variables))
        except JSONDecodeError:
            return data_template.render(**self.user._variables)
        except KeyError:
            return loads(data_template.render())
