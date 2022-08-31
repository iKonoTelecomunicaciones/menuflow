from __future__ import annotations

from typing import Dict, List, Optional

from attr import dataclass, ib

from mautrix.types import SerializableAttrs

from .message import Message
from .pipeline import Pipeline
from .utils.base_logger import BaseLogger
from .variable import Variable


@dataclass
class Menu(SerializableAttrs, BaseLogger):
    id: str = ib(metadata={"json": "id"})
    global_variables: Optional[List[Variable]] = ib(
        metadata={"json": "global_variables"}, factory=list
    )
    messages: List[Message] = ib(metadata={"json": "messages"}, factory=list)
    pipelines: List[Pipeline] = ib(metadata={"json": "pipelines"}, factory=list)

    message_by_id: Dict[str, Message] = {}
    pipeline_by_id: Dict[str, Pipeline] = {}

    def get_message_by_id(self, message_id: str) -> "Message" | None:
        """ "If the message is in the cache, return it. Otherwise,
        search the list of messages for the message with the given ID,
        and if it's found, add it to the cache and return it."

        The first line of the function is a try/except block.
        If the message is in the cache, the first line will return it.
        If the message is not in the cache, the first line will raise a KeyError exception,
        which will be caught by the except block

        Parameters
        ----------
        message_id : str
            The ID of the message to get.

        Returns
        -------
            A message object

        """

        try:
            return Message.deserialize(self.message_by_id[message_id].serialize())
        except KeyError:
            pass

        for message in self.messages:
            if message_id == message.id:
                self.message_by_id[message_id] = message
                return Message.deserialize(message.serialize())

    def get_pipeline_by_id(self, pipeline_id: str) -> "Pipeline" | None:
        """If the pipeline is in the cache, return it.
        Otherwise, search the list of pipelines for the pipeline with the given ID,
        and if found, add it to the cache and return it

        Parameters
        ----------
        pipeline_id : str
            The ID of the pipeline you want to get.

        Returns
        -------
            A pipeline object

        """

        try:
            return Pipeline.deserialize(self.pipeline_by_id[pipeline_id].serialize())
        except KeyError:
            pass

        for pipeline in self.pipelines:
            if pipeline_id == pipeline.id:
                self.pipeline_by_id[pipeline_id] = pipeline
                return Pipeline.deserialize(pipeline.serialize())
