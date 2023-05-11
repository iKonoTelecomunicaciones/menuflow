from __future__ import annotations

from typing import Any, Dict

from attr import dataclass, ib
from mautrix.types import SerializableAttrs

from ..flow_object import FlowObject


@dataclass
class Auth(SerializableAttrs):
    method: str = ib(default=None)
    token_path: str = ib(default=None)
    attempts: int = ib(default=None)
    headers: Dict[str, Any] = ib(default=None)
    cookies: Dict[str, Any] = ib(factory=dict)
    data: Dict[str, Any] = ib(default=None)
    json: Dict[str, Any] = ib(default=None)
    query_params: Dict[str, Any] = ib(default=None)
    variables: Dict[str, Any] = ib(default=None)
    token_path: str = ib(default=None)
    basic_auth: Dict[str, Any] = ib(default=None)


@dataclass
class General(SerializableAttrs):
    headers: Dict[str, Any] = ib(default=None)


@dataclass
class HTTPMiddleware(FlowObject):
    """
    ## HTTPMiddleware

    An HTTPMiddleware define what to do before HTTP request will send.
    You can have more than one middleware on your flow, each one is specific by URL,
    it only applies for the requests that start by the URL define in the middleware.

    content:

    ```
    middlewares:

        -   id: api_jwt
            type: jwt
            url: "https://webapinet.userfoo.com/api"
            token_type: 'Bearer'
            auth:
                method: POST
                token_path: /login/authenticate
                headers:
                    content-type: application/json
                data:
                    username: "foo"
                    password: "secretfoo"
                variables:
                    token: token
            general:
                headers:
                    content-type: application/json

        -   id: api_basic
            url: "https://dev.foo.com.co/customers_list"
            type: basic
            auth:
                basic_auth:
                    login: admin
                    password: secretfoo
            general:
                headers:
                    content-type: application/x-www-form-urlencoded
    ```
    """

    url: str = ib(default=None)
    token_type: str = ib(default=None)
    auth: Auth = ib(default=None)
    general: General = ib(default=None)
