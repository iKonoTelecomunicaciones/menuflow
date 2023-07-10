from attr import dataclass, ib
from mautrix.types import SerializableAttrs


@dataclass
class EmailServer(SerializableAttrs):
    """
    ## EmailServer

    Email server configuration, it is the base to start an email client.
    You can have more than one email server, each one is specific by ID.
    Email servers are general for all flows that want to use it.

    email_servers:
    -   server_id: sample-server-1
        host: smtp.server1.com
        port: 587
        start_tls: true
        username: user1
        password: pass1
    -   server_id: sample-server-2
        host: smtp.server2.com
        port: 25
        username: user2
        password: pass2
    """

    server_id: str = ib(factory=str)
    host: str = ib(factory=str)
    port: int = ib(factory=int)
    start_tls: bool = ib(default=True)
    username: str = ib(factory=str)
    password: str = ib(factory=str)
