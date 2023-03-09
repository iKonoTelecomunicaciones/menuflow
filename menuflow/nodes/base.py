from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from json import JSONDecodeError, dumps, loads
from logging import getLogger
from typing import Any, Dict, List

from aiohttp import ClientSession
from mautrix.client import Client as MatrixClient
from mautrix.util.logging import TraceLogger

from ..config import Config
from ..jinja.jinja_template import jinja_env


class NodeType(Enum):
    MESSAGE = "message"
    SWITCH = "switch"
    INPUT = "input"
    HTTPREQUEST = "http_request"
    CHECKTIME = "check_time"


class Base:

    log: TraceLogger = getLogger("menuflow.node")

    config: Config
    matrix_client: MatrixClient
    session: ClientSession

    data: Dict
    variables: Dict = {}

    @property
    def id(self) -> str:
        return self.data.get("id", "")

    @property
    def type(self) -> NodeType:
        return NodeType(self.data.get("type", ""))

    @classmethod
    def init_cls(cls, config: Config, matrix_client: MatrixClient, variables: Dict):
        cls.config = config
        cls.matrix_client = matrix_client
        cls.session = matrix_client.api.session
        cls.variables = variables

    @abstractmethod
    async def run(self):
        pass

    def render_data(self, data: Dict | List | str, variables: Dict) -> Dict | List | str:
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

        variables: Dict[str, Any] = {}
        variables.update(variables)
        # if self.flow_variables:
        #     variables.update(self.flow_variables.__dict__)

        if isinstance(data, str):
            data_template = jinja_env.from_string(data)
        else:
            try:
                data_template = jinja_env.from_string(dumps(data))
            except Exception as e:
                self.log.exception(e)
                return

        def convert_to_bool(item):
            if isinstance(item, dict):
                for k, v in item.items():
                    item[k] = convert_to_bool(v)
                return item
            elif isinstance(item, list):
                return [convert_to_bool(i) for i in item]
            elif isinstance(item, str):
                if item in ["True", "true"]:
                    return True
                elif item in ["False", "false"]:
                    return False
                else:
                    return item
            else:
                return item

        try:
            data = loads(data_template.render(**variables))
            data = convert_to_bool(data)
            return data
        except JSONDecodeError:
            data = data_template.render(**variables)
            return convert_to_bool(data)
        except KeyError:
            data = loads(data_template.render())
            data = convert_to_bool(data)
            return data
