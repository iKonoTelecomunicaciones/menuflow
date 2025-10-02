import logging

from mautrix.util.logging import TraceLogger
from nats import connect as nats_connect
from nats.aio.client import Client as NATSClient
from nats.js.api import RetentionPolicy, StreamConfig
from nats.js.client import JetStreamContext
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
            allow_reconnect=True,
            max_reconnect_attempts=3,
            user=cls.config["nats.user"],
            password=cls.config["nats.password"],
            name=f"MENUFLOW {cls.config['homeserver.domain']} {cls.config['nats.user']}",
        )
        js = nc.jetstream()

        # Set the original stream configuration
        stream_name = cls.config["nats.stream"]
        subject = f"{cls.config['nats.subject']}.*"
        stream_config = StreamConfig(name=stream_name, subjects=[subject])

        # Set the CEP stream configuration
        cep_stream_name = cls.config["nats.stream"] + "_CEP"
        cep_subject = f"{cls.config['nats.subject']}_cep.*"
        cep_stream_config = StreamConfig(
            name=cep_stream_name,
            subjects=[cep_subject],
            retention=RetentionPolicy.WORK_QUEUE,
            num_replicas=cls.config["nats.num_replicas"],
        )

        # Set the MNTR stream configuration
        mntr_stream_name = cls.config["nats.stream"] + "_MNTR"
        mntr_subject = f"{cls.config['nats.subject']}_mntr.*"
        mntr_stream_config = StreamConfig(
            name=mntr_stream_name,
            subjects=[mntr_subject],
            retention=RetentionPolicy.INTEREST,
            num_replicas=cls.config["nats.num_replicas"],
            max_age=24 * 60 * 60,  # Keep messages for 1 day maximum (in seconds)
        )

        await cls.stream_handler(
            config_list=[stream_config, cep_stream_config, mntr_stream_config], js=js
        )

        return nc, js

    @classmethod
    async def close_connection(cls):
        if cls._nats_conn:
            log.info("Closing NATS connection")
            await cls._nats_conn.close()
            cls._nats_conn = None

    @classmethod
    async def stream_handler(cls, config_list: list[StreamConfig], js: JetStreamContext) -> None:
        """
        This function checks if the stream exists, if exists then update it, if not then create it
        """

        for config in config_list:
            log.info(f"Handling stream: {config.name} with subjects: {config.subjects}...")
            stream_exists = None

            try:
                stream_exists = await js.stream_info(
                    name=config.name, subjects_filter=config.subjects[0]
                )
                log.info(f"Stream {config.name} already exists")
            except ServerError as e:
                log.error(f"Error getting stream info: {e.err_code} - {e.description}")

            if not stream_exists:
                log.info(f"Stream {config.name} does not exist, creating...")
                try:
                    await js.add_stream(config=config)
                except ServerError as e:
                    log.error(f"Error creating stream: {e.err_code} - {e.description}")
                    log.info(f"Retrying to create stream {config.name}...")
                    config.num_replicas = None
                    await js.add_stream(config=config)

                log.info(f"Stream {config.name} created successfully")
                continue

            try:
                log.info(f"Updating stream {config.name}...")
                await js.update_stream(config=config)
            except ServerError as e:
                log.error(f"Error updating stream: {e.err_code} - {e.description}")
                log.info(f"Retrying to update stream {config.name}...")
                config.num_replicas = None
                await js.update_stream(config=config)

            log.info(f"Stream {config.name} updated successfully")
