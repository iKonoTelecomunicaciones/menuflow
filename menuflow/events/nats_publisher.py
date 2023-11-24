import logging

from mautrix.util.logging import TraceLogger
from nats import connect as nats_connect
from nats.aio.client import Client as NATSClient
from nats.js.client import JetStreamContext

from ..config import Config

log: TraceLogger = logging.getLogger("menuflow.nats")


class NatsPublisher:
    _nats_conn: NATSClient = None
    _jetstream_conn: JetStreamContext = None
    config: Config = None

    @classmethod
    def init_cls(cls, config: Config):
        cls.config = config

    @classmethod
    async def get_connection(cls) -> tuple[NATSClient, JetStreamContext]:
        if not cls._nats_conn or cls._nats_conn and cls._nats_conn.is_closed:
            try:
                cls._nats_conn, cls._jetstream_conn = await cls.nats_jetstream_connection()
            except Exception as e:
                log.error(f"Error connecting to NATS: {e}")
                return None, None

        return cls._nats_conn, cls._jetstream_conn

    @classmethod
    async def nats_jetstream_connection(cls) -> JetStreamContext:
        log.info("Connecting to NATS JetStream")
        nc: NATSClient = await nats_connect(
            cls.config["nats.address"], allow_reconnect=False, max_reconnect_attempts=1
        )
        js = nc.jetstream()
        subject = f"{cls.config['nats.subject']}.*"
        await js.add_stream(name="menuflow", subjects=[subject])
        return nc, js

    @classmethod
    async def close_connection(cls):
        if cls._nats_conn:
            log.info("Closing NATS connection")
            await cls._nats_conn.close()
            cls._nats_conn = None
