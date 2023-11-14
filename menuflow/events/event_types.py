from mautrix.types import SerializableEnum


class MenuflowEventTypes(SerializableEnum):
    NODE = "NODE"


class MenuflowNodeEvents(SerializableEnum):
    NodeEntry = "NodeEntry"
    NodeInputData = "NodeInputData"
    NodeInputTimeout = "NodeInputTimeout"
