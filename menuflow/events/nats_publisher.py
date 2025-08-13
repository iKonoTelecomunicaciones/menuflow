import logging

from mautrix.util.logging import TraceLogger
from nats import connect as nats_connect
from nats.aio.client import Client as NATSClient
from nats.js.client import JetStreamContext
from nats.js.api import RetentionPolicy, StreamConfig
from nats.js.errors import ServerError

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
            cls.config["nats.address"],
            allow_reconnect=False,
            max_reconnect_attempts=1,
            user=cls.config["nats.user"],
            password=cls.config["nats.password"],
            name=f"MENUFLOW {cls.config['homeserver.domain']} {cls.config['nats.user']}",
        )
        js = nc.jetstream()
        subject = f"{cls.config['nats.subject']}.*"
        cep_subject = f"{cls.config['nats.subject']}_cep.*"
        mntr_subject = f"{cls.config['nats.subject']}_mntr.*"

        stream_config = StreamConfig(name=cls.config["nats.stream"], subjects=[subject])
        cep_stream_config = StreamConfig(
            name=cls.config["nats.stream"] + "_CEP",
            subjects=[cep_subject],
            retention=RetentionPolicy.WORK_QUEUE,
            num_replicas=cls.config["nats.num_replicas"],
        )
        mntr_stream_config = StreamConfig(
            name=cls.config["nats.stream"] + "_MNTR",
            subjects=[mntr_subject],
            retention=RetentionPolicy.INTEREST,
            num_replicas=cls.config["nats.num_replicas"],
            max_age=24 * 60 * 60,  # Keep messages for 1 day maximum (in seconds)
        )

        try:
            await js.add_stream(config=stream_config)
            await js.add_stream(config=cep_stream_config)
            await js.add_stream(config=mntr_stream_config)
        except ServerError as e:
            log.critical(f"Error adding stream: {e.err_code} - {e.description}")
            cep_stream_config.num_replicas = None
            mntr_stream_config.num_replicas = None
            await js.add_stream(config=cep_stream_config)
            await js.add_stream(config=mntr_stream_config)

        return nc, js

    @classmethod
    async def close_connection(cls):
        if cls._nats_conn:
            log.info("Closing NATS connection")
            await cls._nats_conn.close()
            cls._nats_conn = None
