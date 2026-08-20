from __future__ import annotations

import html
import json
import mimetypes
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import openai
from mautrix.types import MessageEvent, MessageType
from mautrix.util.magic import mimetype

from ..db.route import RouteState
from ..repository import GPTAssistant as GPTAssistantModel
from ..room import Room
from ..utils import Middlewares, Util
from ..utils.types import Scopes
from .input import Input
from .switch import Switch

if TYPE_CHECKING:
    from ..middlewares import ASRMiddleware, TTMMiddleware

_STATE_KEY = "gpt_state"


class GPTMode(str, Enum):
    RESPONSES = "responses"
    ASSISTANTS = "assistants"


@dataclass
class ConversationState:
    history: list[dict[str, Any]] = field(default_factory=list)
    # Assistants mode (legacy): OpenAI Thread/Assistant IDs
    thread_id: str | None = None
    assistant_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationState:
        return cls(
            history=list[dict[str, Any]](data.get("history", [])),
            thread_id=data.get("thread_id"),
            assistant_id=data.get("assistant_id"),
        )


class GPTAssistant(Switch):
    _CLIENTS: dict[str, openai.AsyncOpenAI] = {}
    OPENAI_TIMEOUT: float = 60.0
    HISTORY_MAX_MESSAGES: int = 50
    ASSISTANT_ID_PREFIX: str = "asst_"
    JSON_PATTERN: re.Pattern[str] = re.compile(r"```json(.*?)```", re.DOTALL)

    def __init__(
        self, gpt_assistant_node_data: GPTAssistantModel, room: Room, default_variables: dict
    ) -> None:
        Switch.__init__(
            self,
            switch_node_data=gpt_assistant_node_data,
            room=room,
            default_variables=default_variables,
        )
        self.log = self.log.getChild(gpt_assistant_node_data.get("id"))
        self.content: dict = gpt_assistant_node_data
        self._state_loaded: bool = False
        self.middlewares: list[ASRMiddleware | TTMMiddleware] = []

        self.mode = (
            GPTMode.ASSISTANTS
            if self.assistant_id.startswith(self.ASSISTANT_ID_PREFIX)
            else GPTMode.RESPONSES
        )
        self.state = ConversationState()

        self.client = self._get_client(self.api_key)

    @classmethod
    def _get_client(cls, api_key: str) -> openai.AsyncOpenAI:
        """Return a shared AsyncOpenAI client for this API key.

        Clients are cached on the class so rooms reuse the same HTTP
        connection pool and timeout (``OPENAI_TIMEOUT``).

        Parameters
        ----------
        api_key : str
            OpenAI API key used as cache key.

        Returns
        -------
        openai.AsyncOpenAI
            Existing client for this key, or a newly created one.
        """
        client = cls._CLIENTS.get(api_key)
        if client is None:
            client = openai.AsyncOpenAI(api_key=api_key, timeout=cls.OPENAI_TIMEOUT)
            cls._CLIENTS[api_key] = client
        return client

    @property
    def name(self) -> str:
        return self.render_data(data=self.content.get("name", ""))

    @property
    def instructions(self) -> str:
        return self.render_data(data=self.content.get("instructions", ""))

    @property
    def model(self) -> str:
        return (
            self.render_data(data=self.content.get("model", ""))
            or self.assistant_id
            or "gpt-4o-mini"
        )

    @property
    def assistant_id(self) -> str:
        return self.render_data(data=self.content.get("assistant_id", ""))

    @property
    def api_key(self) -> str:
        return self.render_data(data=self.content.get("api_key", ""))

    @property
    def initial_info(self) -> str:
        return self.render_data(self.content.get("initial_info", ""))

    @property
    def variable(self) -> str:
        return self.render_data(self.content.get("variable", ""))

    @property
    def inactivity_options(self) -> dict[str, Any]:
        return Input.inactivity_options.fget(self)

    @property
    def group_messages_timeout(self) -> int:
        return self.render_data(self.content.get("group_messages_timeout", 0))

    @property
    def max_history_messages(self) -> int:
        return self.render_data(
            self.content.get("max_history_messages", self.HISTORY_MAX_MESSAGES)
        )

    async def _resolve_assistant_id(self) -> str:
        """Return the Assistants API assistant ID, creating one if needed.

        Preference order: node config ``assistant_id``, then the ID already
        persisted in ``self.state``, then ``beta.assistants.create``.

        Returns
        -------
        str
            OpenAI assistant ID (usually prefixed with ``asst_``).
        """
        if configured := self.assistant_id:
            self.state.assistant_id = configured
            return configured

        if self.state.assistant_id:
            return self.state.assistant_id

        assistant = await self.client.beta.assistants.create(
            name=self.name,
            instructions=self.instructions,
            tools=[{"type": "code_interpreter"}],
            model=self.model,
        )
        self.state.assistant_id = assistant.id
        return assistant.id

    async def _resolve_thread_id(self) -> str:
        """Return the Assistants API thread ID for this room, creating one if needed.

        Reuses ``self.state.thread_id`` when present; otherwise creates a
        new thread and stores its ID on the in-memory state.

        Returns
        -------
        str
            OpenAI thread ID.
        """
        if self.state.thread_id:
            return self.state.thread_id

        thread = await self.client.beta.threads.create()
        self.state.thread_id = thread.id
        return thread.id

    async def _ensure_assistants_ready(self) -> tuple[str, str]:
        """Load persisted state and guarantee assistant and thread IDs exist.

        If either ID changed relative to the previously loaded state, the
        new values are staged into the node scope and flushed with ``Scopes.NODE``.

        Returns
        -------
        tuple[str, str]
            ``(assistant_id, thread_id)`` ready for ``runs.create_and_poll``.
        """
        self._load_state()
        previous_ids = (self.state.assistant_id, self.state.thread_id)

        try:
            assistant_id = await self._resolve_assistant_id()
            thread_id = await self._resolve_thread_id()
        except openai.APIError as exc:
            self.log.error(f"[{self.room.room_id}] Failed to initialize Assistants mode: {exc}")
            raise

        if (self.state.assistant_id, self.state.thread_id) != previous_ids:
            await self._save_state()

        self.log.debug(
            f"[{self.room.room_id}] Assistants ready "
            f"(assistant={assistant_id}, thread={thread_id})"
        )
        return assistant_id, thread_id

    def _load_state(self) -> None:
        """Hydrate ``self.state`` from the node scope once per instance.

        Reads ``gpt_state`` from ``Scopes.NODE``. Subsequent calls are no-ops
        while ``_state_loaded`` is True, so callers can invoke this freely.
        """
        if self._state_loaded:
            return

        persisted = self.room.scope.get(Scopes.NODE).get(_STATE_KEY)
        if isinstance(persisted, dict) and persisted:
            self.state = ConversationState.from_dict(persisted)
            self.log.debug(
                f"[{self.room.room_id}] Restored GPT state from node scope "
                f"(history={len(self.state.history)}, thread_id={self.state.thread_id!r})"
            )

        self._state_loaded = True

    async def _save_state(self) -> None:
        """Persist the current conversation into node variables as ``gpt_state``.

        Stages into the node scope and flushes to the database immediately.
        """
        self.room.set_node_var(**{_STATE_KEY: self.state.to_dict()})
        await self.room.scope.update(Scopes.NODE)
        self.log.debug(
            f"[{self.room.room_id}] Persisted GPT state to node scope "
            f"(history={len(self.state.history)}, thread_id={self.state.thread_id!r})"
        )

    def _file_purpose(self, *, for_vision: bool) -> str:
        """Return the OpenAI Files API purpose for the active mode.

        Responses mode always uses ``user_data``. Assistants mode uses
        ``vision`` for image inputs.
        """
        if self.mode == GPTMode.ASSISTANTS and for_vision:
            return "vision"
        return "user_data"

    @property
    def _file_expiry_seconds(self) -> int | None:
        secs = self.config.get("menuflow.openai.file_expiry_seconds", 0)
        if not secs:
            return None
        return max(3600, min(int(secs), 604800))

    def _trim_history(self) -> None:
        """Keep the Responses-mode history within ``max_history_messages``.

        System messages are always retained. The remaining budget is filled
        with the most recent non-system messages. No-op when already within the limit.
        """
        limit = self.max_history_messages
        if len(self.state.history) <= limit:
            return

        system = [m for m in self.state.history if m.get("role") == "system"]
        rest = [m for m in self.state.history if m.get("role") != "system"]
        keep = max(0, limit - len(system))
        self.state.history = system + rest[-keep:]

    def _text_content_block(self, text: str) -> dict[str, Any]:
        """Build a text part in the format expected by the active API mode.

        Parameters
        ----------
        text : str
            Plain user or transcribed text.

        Returns
        -------
        dict[str, Any]
            ``input_text`` block in Responses mode, ``text`` block in Assistants mode.
        """
        if self.mode == GPTMode.RESPONSES:
            return {"type": "input_text", "text": text}
        return {"type": "text", "text": text}

    async def _upload_openai_file(
        self, *, file_name: str, data: bytes, mime: str, purpose: str
    ) -> str | None:
        """Upload raw bytes to OpenAI Files and return the resulting file ID.

        Parameters
        ----------
        file_name : str
            Filename sent to OpenAI.
        data : bytes
            File contents downloaded from Matrix.
        mime : str
            MIME type of ``data``.
        purpose : str
            OpenAI upload purpose, e.g. ``user_data`` or ``vision``.

        Returns
        -------
        str | None
            Uploaded file ID, or ``None`` if the API call failed (already logged).
        """
        try:
            kwargs: dict[str, Any] = {"file": (file_name, data, mime), "purpose": purpose}
            if (secs := self._file_expiry_seconds) is not None:
                kwargs["expires_after"] = {"anchor": "created_at", "seconds": secs}
            uploaded = await self.client.files.create(**kwargs)
        except openai.APIError as exc:
            self.log.error(f"[{self.room.room_id}] Failed to upload file: {exc}")
            return None
        return uploaded.id

    async def _download_media(self, evt: MessageEvent) -> tuple[bytes, str]:
        """Download a Matrix media file and return the raw bytes and mimetype."""
        data = await self.room.matrix_client.download_media(evt.content.url)
        mime = getattr(evt.content.info, "mimetype", None) or mimetype(data)
        return data, mime

    async def _build_content_block(self, evt: MessageEvent | str) -> dict[str, Any] | None:
        """Convert a Matrix event (or raw string) into an OpenAI content block.

        Supported types: text, image, PDF file (Responses mode only), and
        audio (via ASR middleware). Other types are logged and skipped.

        Parameters
        ----------
        evt : MessageEvent | str
            Incoming room event, or a plain string treated as text.

        Returns
        -------
        dict[str, Any] | None
            Mode-specific content block, or ``None`` when the type is
            unsupported or conversion failed.
        """
        if isinstance(evt, str) or evt.content.msgtype == MessageType.TEXT:
            message = evt if isinstance(evt, str) else evt.content.body
            return self._text_content_block(message)

        if evt.content.msgtype == MessageType.IMAGE:
            return await self._image_content_block(evt)

        if evt.content.msgtype == MessageType.FILE and self.mode == GPTMode.RESPONSES:
            return await self._file_content_block(evt)

        if evt.content.msgtype == MessageType.AUDIO:
            text = await self._transcribe_audio(evt)
            return self._text_content_block(text) if text else None

        self.log.warning(
            f"[{self.room.room_id}] Unsupported message type: "
            f"{getattr(evt.content, 'msgtype', type(evt))}"
        )
        return None

    async def _image_content_block(self, evt: MessageEvent) -> dict[str, Any] | None:
        """Download a Matrix image, upload it for vision, and return the content block.
        Uses the original filename unless the body looks forwarded, in which
        case a name is derived from the detected MIME type.

        Parameters
        ----------
        evt : MessageEvent
            Image message whose ``content.url`` points to Matrix media.

        Returns
        -------
        dict[str, Any] | None
            ``input_image`` (Responses) or ``image_file`` (Assistants),
            or ``None`` if the upload failed.
        """
        matrix_file, file_mimetype = await self._download_media(evt)

        if evt.content.body and "forwarded" not in evt.content.body.lower():
            file_name = evt.content.body
        else:
            extension = mimetypes.guess_extension(file_mimetype) or ".bin"
            file_name = f"image{extension}"

        file_id = await self._upload_openai_file(
            file_name=file_name,
            data=matrix_file,
            mime=file_mimetype,
            purpose=self._file_purpose(for_vision=True),
        )
        if not file_id:
            return None

        if self.mode == GPTMode.RESPONSES:
            return {"type": "input_image", "file_id": file_id}
        return {"type": "image_file", "image_file": {"file_id": file_id}}

    async def _file_content_block(self, evt: MessageEvent) -> dict[str, Any] | None:
        """Build a Responses-mode PDF block from a Matrix file message.

        Only ``application/pdf`` is accepted. The file is uploaded with
        purpose ``user_data``.

        Parameters
        ----------
        evt : MessageEvent
            File message to convert.

        Returns
        -------
        dict[str, Any] | None
            ``input_file`` block, or ``None`` if the MIME type is not PDF
            or the upload failed.
        """
        if (_mimetype := getattr(evt.content.info, "mimetype", None)) != "application/pdf":
            self.log.warning(f"[{self.room.room_id}] Unsupported file mimetype: {_mimetype}")
            return None

        matrix_file, file_mimetype = await self._download_media(evt)

        file_name = evt.content.body if evt.content.body else "document.pdf"
        file_id = await self._upload_openai_file(
            file_name=file_name,
            data=matrix_file,
            mime=file_mimetype,
            purpose=self._file_purpose(for_vision=False),
        )
        if not file_id:
            return None

        return {"type": "input_file", "file_id": file_id}

    async def _transcribe_audio(self, evt: MessageEvent) -> str | None:
        """Transcribe a Matrix audio message using the configured ASR middleware.

        Parameters
        ----------
        evt : MessageEvent
            Audio message with a media URL.

        Returns
        -------
        str | None
            Transcript text, or ``None`` if no ASR middleware is configured
            or transcription fails.
        """
        if not self.middlewares:
            self.log.warning(
                f"[{self.room.room_id}] Audio received but no ASR middleware configured"
            )
            return None

        middlewares_sorted = {
            Middlewares(middleware.type): middleware for middleware in self.middlewares
        }
        asr = middlewares_sorted.get(Middlewares.ASR)
        if asr is None:
            self.log.warning(f"[{self.room.room_id}] ASR middleware not found")
            return None

        audio_name = evt.content.file or "audio.ogg"
        _, text = await asr.run(audio_url=evt.content.url, audio_name=audio_name)
        return text

    async def add_message(self, messages: list[MessageEvent | str]) -> bool:
        """Append user content to the conversation (history or Assistants thread).

        Each event is converted with ``_build_content_block``. Empty or
        unsupported batches return ``False`` and leave state unchanged.
        In Responses mode the blocks are stored in ``state.history``.
        In Assistants mode they are posted to the OpenAI thread.

        Parameters
        ----------
        messages : list[MessageEvent | str]
            Events (or strings) that belong to the current user turn.

        Returns
        -------
        bool
            ``True`` if at least one block was stored or posted.
        """
        self._load_state()

        blocks: list[dict[str, Any]] = []
        for event in messages:
            if block := await self._build_content_block(event):
                blocks.append(block)

        if not blocks:
            return False

        if self.mode == GPTMode.RESPONSES:
            self.state.history.append({"role": "user", "content": blocks})
            await self._save_state()
            return True

        _, thread_id = await self._ensure_assistants_ready()
        try:
            await self.client.beta.threads.messages.create(
                thread_id=thread_id, role="user", content=blocks
            )
        except openai.APIError as exc:
            self.log.error(f"[{self.room.room_id}] Failed to add message to thread: {exc}")
            return False

        return True

    async def run_assistant(self) -> str | dict | list:
        """Generate the next assistant reply using the API selected by ``self.mode``.

        Returns
        -------
        str | dict | list
            Parsed assistant output, or an empty string on API failure.
        """
        if self.mode == GPTMode.RESPONSES:
            return await self._run_responses()
        return await self._run_assistants()

    async def _run_responses(self) -> str | dict | list:
        """Call the OpenAI Responses API with the persisted message history.

        If history is empty, a placeholder ``Hello`` user turn is sent.
        A successful text reply is appended to history, parsed, trimmed,
        and staged back into the node scope.

        Returns
        -------
        str | dict | list
            Parsed output, or ``""`` if ``responses.create`` failed.
        """
        self._load_state()

        input_messages = self.state.history.copy()
        if not input_messages:
            input_messages = [
                {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}
            ]

        kwargs: dict[str, Any] = {"model": self.model, "input": input_messages}
        if instr := self.instructions:
            kwargs["instructions"] = instr

        try:
            ai_response = await self.client.responses.create(**kwargs)
        except openai.APIError as exc:
            status = getattr(exc, "status_code", "unknown")
            self.log.error(
                f"[{self.room.room_id}] Error creating Responses API reply (status={status}): {exc}"
            )
            return ""

        assistant_message = ai_response.output_text or ""
        if assistant_message:
            self.state.history.append(
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": assistant_message}],
                }
            )
            assistant_message = self.parse_openai_output(assistant_message)

        self._trim_history()
        await self._save_state()
        return assistant_message

    async def _run_assistants(self, instructions: str | None = None) -> str | dict | list:
        """Create and poll an Assistants run, then extract the latest reply.

        Parameters
        ----------
        instructions : str | None
            Optional per-run instructions that override the assistant defaults.

        Returns
        -------
        str | dict | list
            Parsed assistant text, or ``""`` if the run fails or does not complete.
        """
        assistant_id, thread_id = await self._ensure_assistants_ready()

        run_kwargs: dict[str, Any] = {"thread_id": thread_id, "assistant_id": assistant_id}
        if instructions:
            run_kwargs["instructions"] = instructions

        try:
            run = await self.client.beta.threads.runs.create_and_poll(
                **run_kwargs, poll_interval_ms=2000
            )
        except openai.APIError as exc:
            status = getattr(exc, "status_code", "unknown")
            self.log.error(
                f"[{self.room.room_id}] Error creating Assistants run " f"(status={status}): {exc}"
            )
            return ""

        if run.status != "completed":
            self.log.error(
                f"[{self.room.room_id}] Assistants run ended with status={run.status!r}"
            )
            return ""

        assistant_message = await self._extract_thread_reply(thread_id)
        if assistant_message:
            assistant_message = self.parse_openai_output(assistant_message)

        await self._save_state()
        return assistant_message

    async def _extract_thread_reply(self, thread_id: str) -> str:
        """Return the concatenated text of the latest assistant message on a thread.

        Lists the most recent messages (desc, limit 5) and joins ``text``
        blocks from the first assistant message found.

        Parameters
        ----------
        thread_id : str
            OpenAI thread to inspect.

        Returns
        -------
        str
            Assistant text, or ``""`` if listing fails or no assistant message exists.
        """
        try:
            messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id, order="desc", limit=5
            )
        except openai.APIError as exc:
            self.log.error(f"[{self.room.room_id}] Failed to list thread messages: {exc}")
            return ""

        for message in messages.data:
            if message.role != "assistant":
                continue
            parts: list[str] = []
            for block in message.content:
                if getattr(block, "type", None) == "text":
                    parts.append(block.text.value)
            return "".join(parts)
        return ""

    def parse_openai_output(self, text: str) -> str | dict | list:
        """Parse assistant text, unwrapping a JSON object or array when possible.

        If the payload is fenced with `` ```json ``, the inner body is used.
        HTML entities are unescaped before ``json.loads``. Non-JSON text is
        returned unchanged.

        Parameters
        ----------
        text : str
            Raw assistant output.

        Returns
        -------
        str | dict | list
            Parsed JSON object/array, or the original string.
        """
        if match := self.JSON_PATTERN.search(text):
            text = html.unescape(match.group(1).strip())

        try:
            parsed_json = json.loads(text)
            if isinstance(parsed_json, (dict, list)):
                return parsed_json
        except (json.JSONDecodeError, TypeError):
            pass

        return text

    async def run(self, messages: list[MessageEvent] | None = None) -> None:
        """If the room is in input mode, then set the variable.
        Otherwise, show the message and enter input mode

        Parameters
        ----------
        evt : Optional[MessageEvent]
            The event that triggered the node.

        """
        if messages is not None and not isinstance(messages, list):
            messages = [messages]

        _inactivity = self.inactivity_options
        _variable = self.variable
        if self.room.route.state == RouteState.INPUT:
            if not messages:
                self.log.warning(f"[{self.room.room_id}] A problem occurred getting message event")
                return

            has_content = await self.add_message(messages)
            if not has_content:
                return

            response = await self.run_assistant()
            await self.room.scope.update(Scopes.NODE)
            await self.room.set_variable(_variable, value=response)

            if _inactivity.get("active"):
                await Util.cancel_task(task_name=self.room.room_id)

            output = await Switch.run(self, update_state=False, generate_event=False)
            o_connection = output if output else self.id
            await self.room.update_menu(o_connection)

        elif self.room.route.state == RouteState.TIMEOUT:
            o_connection = await self.get_case_by_id("timeout")
            await self.room.update_menu(node_id=o_connection, state=None)

        else:
            # This is the case where the room is not in the input state
            # and the node is an input node.
            # In this case, the message is shown and the menu is updated to the node's id
            # and the room state is set to input.
            self.log.debug(f"[{self.room.room_id}] Entering gpt_assistant node {self.id}")

            if not await self.room.get_variable(_variable):
                if _initial_info := self.initial_info:
                    await self.add_message([_initial_info])

                response = await self.run_assistant()
                await self.room.set_variable(_variable, value=response)

            message = await self.room.get_variable(_variable)
            await self.room.matrix_client.send_text(room_id=self.room.room_id, text=message)
            await self.room.update_menu(
                node_id=self.id, state=RouteState.INPUT, update_node_vars=False
            )
