from __future__ import annotations

from abc import abstractmethod
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from typing import Dict, List

from aiohttp import ClientSession
from mautrix.client import Client as MatrixClient
from mautrix.util.logging import TraceLogger

from ..config import Config
from ..jinja.jinja_template import jinja_env
from ..room import Room


def convert_to_bool(item) -> Dict | List | str:
    if isinstance(item, dict):
        for k, v in item.items():
            item[k] = convert_to_bool(v)
        return item
    elif isinstance(item, list):
        return [convert_to_bool(i) for i in item]
    elif isinstance(item, str):
        if item.lower() == "true":
            return True
        elif item.lower() == "false":
            return False
        else:
            return item
    else:
        return item


class Base:
    log: TraceLogger = getLogger("menuflow.node")

    config: Config
    matrix_client: MatrixClient
    session: ClientSession

    data: Dict
    room: Room

    @property
    def id(self) -> str:
        return self.data.get("id", "")

    @property
    def type(self) -> str:
        return self.data.get("type", "")

    @classmethod
    def init_cls(cls, config: Config, matrix_client: MatrixClient, default_variables: Dict):
        cls.config = config
        cls.matrix_client = matrix_client
        cls.session = matrix_client.api.session
        cls.variables = default_variables or {}

    @abstractmethod
    async def run(self):
        pass

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

        self.variables.update(self.room._variables)

        try:
            data = loads(data_template.render(**self.variables))
            data = convert_to_bool(data)
            return data
        except JSONDecodeError:
            data = data_template.render(**self.variables)
            return convert_to_bool(data)
        except KeyError:
            data = loads(data_template.render())
            data = convert_to_bool(data)
            return data
