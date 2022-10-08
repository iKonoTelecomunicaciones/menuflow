from logging import getLogger

from mautrix.util.logging import TraceLogger


class BaseLogger:
    log: TraceLogger = getLogger("menuflow.node")
