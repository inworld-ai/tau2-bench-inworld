"""Inworld Realtime API provider for real-time voice processing.

Uses WebSocket for bidirectional audio streaming with the Inworld Realtime API.
The wire protocol is OpenAI-Realtime-compatible with three notable differences:

1. **Auth:** ``Authorization: Basic <api_key>`` (the key is already base64-encoded
   from the Inworld Portal; do NOT base64-encode it again).
2. **URL:** ``wss://api.inworld.ai/api/v1/realtime/session`` with required query
   params ``key=voice-<timestamp_ms>`` and ``protocol=realtime``.
3. **Audio:** PCM16 at 24 kHz only. ``audio/pcmu`` requests are silently
   coerced to PCM. Conversion from telephony μ-law is done by the adapter.

Session config places audio settings under nested input/output objects, with
``semantic_vad`` turn detection (``eagerness``) and TTS engine + voice
selected under ``audio.output``.

Reference: https://docs.inworld.ai/api-reference/realtimeAPI/realtime/realtime-websocket
"""

import asyncio
import base64
import json
import os
import time
from enum import Enum
from typing import AsyncGenerator, Dict, List, Optional

import websockets
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel

from tau2.config import (
    DEFAULT_INWORLD_EAGERNESS,
    DEFAULT_INWORLD_MODEL,
    DEFAULT_INWORLD_OUTPUT_SAMPLE_RATE,
    DEFAULT_INWORLD_REALTIME_STT_LANGUAGE,
    DEFAULT_INWORLD_REALTIME_STT_MODEL,
    DEFAULT_INWORLD_REALTIME_URL,
    DEFAULT_INWORLD_TTS_MODEL,
    DEFAULT_INWORLD_VOICE,
)
from tau2.environment.tool import Tool
from tau2.utils.retry import websocket_retry
from tau2.voice.audio_native.inworld.events import (
    BaseInworldEvent,
    InworldTimeoutEvent,
    InworldUnknownEvent,
    parse_inworld_event,
)

load_dotenv()

# Inworld output format (PCM16 mono @ 24 kHz) — 48000 bytes/sec
INWORLD_OUTPUT_BYTES_PER_SECOND = DEFAULT_INWORLD_OUTPUT_SAMPLE_RATE * 2


class InworldEagerness(str, Enum):
    """Semantic VAD eagerness levels for Inworld Realtime API."""

    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InworldVADConfig(BaseModel):
    """Configuration for Inworld's semantic Voice Activity Detection.

    Attributes:
        eagerness: How aggressively the server detects end-of-turn. Higher
            eagerness → faster turn-taking but more interruptions.
        create_response: Auto-create a response when VAD detects end-of-turn.
        interrupt_response: Allow user audio to interrupt agent response.
    """

    eagerness: InworldEagerness = InworldEagerness(DEFAULT_INWORLD_EAGERNESS)
    create_response: bool = True
    interrupt_response: bool = True


class InworldRealtimeProvider:
    """Inworld Realtime API provider with WebSocket-based communication.

    This provider manages a persistent WebSocket connection to Inworld's
    Realtime API, enabling real-time bidirectional voice agent interaction.

    Attributes:
        api_key: The Inworld API key (already base64-encoded from the portal).
        model: LLM backbone identifier (e.g., ``openai/gpt-4.1-mini``).
        voice: TTS voice name (e.g., ``Clive``).
        tts_model: TTS engine (e.g., ``inworld-tts-1.5-mini``).
        ws: The active WebSocket connection, or None if disconnected.
    """

    BASE_URL = DEFAULT_INWORLD_REALTIME_URL
    DEFAULT_MODEL = DEFAULT_INWORLD_MODEL
    DEFAULT_VOICE = DEFAULT_INWORLD_VOICE
    DEFAULT_TTS_MODEL = DEFAULT_INWORLD_TTS_MODEL
    DEFAULT_EAGERNESS = DEFAULT_INWORLD_EAGERNESS
    DEFAULT_REALTIME_STT_MODEL = DEFAULT_INWORLD_REALTIME_STT_MODEL
    DEFAULT_REALTIME_STT_LANGUAGE = DEFAULT_INWORLD_REALTIME_STT_LANGUAGE

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        tts_model: Optional[str] = None,
        realtime_stt_model: Optional[str] = None,
        realtime_stt_language: Optional[str] = None,
        sample_rate: int = DEFAULT_INWORLD_OUTPUT_SAMPLE_RATE,
    ):
        """Initialize the Inworld Realtime provider.

        Args:
            api_key: Inworld API key. If not provided, reads ``INWORLD_API_KEY``
                from the environment.
            model: LLM backbone (e.g., ``openai/gpt-4.1-mini``). Reads
                ``INWORLD_MODEL`` env var if not provided.
            voice: TTS voice name. Reads ``INWORLD_VOICE`` env var if not
                provided.
            tts_model: TTS engine name. Reads ``INWORLD_TTS_MODEL`` env var if
                not provided.
            realtime_stt_model: In-session STT model that transcribes the user's
                audio for the agent. Goes into ``audio.input.transcription.model``
                in session.update. Reads ``INWORLD_REALTIME_STT_MODEL`` if not
                provided. Examples: ``soniox/stt-rt-v4`` (default),
                ``inworld/inworld-stt-1``, ``assemblyai/u3-rt-pro``,
                ``assemblyai/universal-streaming-english``.
            realtime_stt_language: BCP-47 language hint for the STT model.
                Reads ``INWORLD_REALTIME_STT_LANGUAGE`` if not provided.
            sample_rate: PCM sample rate (24000 — Inworld's only supported
                rate at present).

        Raises:
            ValueError: If no API key is provided or found in environment.
        """
        self.api_key = api_key or os.environ.get("INWORLD_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Inworld API key not provided. Set INWORLD_API_KEY env var."
            )

        self.model = model or os.environ.get("INWORLD_MODEL") or self.DEFAULT_MODEL
        self.voice = voice or os.environ.get("INWORLD_VOICE") or self.DEFAULT_VOICE
        self.tts_model = (
            tts_model
            or os.environ.get("INWORLD_TTS_MODEL")
            or self.DEFAULT_TTS_MODEL
        )
        self.realtime_stt_model = (
            realtime_stt_model
            or os.environ.get("INWORLD_REALTIME_STT_MODEL")
            or self.DEFAULT_REALTIME_STT_MODEL
        )
        self.realtime_stt_language = (
            realtime_stt_language
            or os.environ.get("INWORLD_REALTIME_STT_LANGUAGE")
            or self.DEFAULT_REALTIME_STT_LANGUAGE
        )
        self.sample_rate = sample_rate
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._current_vad_config: Optional[InworldVADConfig] = None
        self.session_id: Optional[str] = None

        # Cached session-config args, populated on the first successful
        # configure_session() call. Used by _ensure_connected() to replay the
        # session after a mid-run websocket disconnect.
        self._session_config_cache: Optional[Dict] = None
        # Single-flight lock so concurrent coroutines (send_audio + the
        # receive loop) don't race on reconnect.
        self._reconnect_lock: Optional[asyncio.Lock] = None
        self._max_reconnect_attempts = 3
        self._reconnect_failures = 0

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket connection is active."""
        if self.ws is None:
            return False
        from websockets.protocol import State

        return self.ws.state == State.OPEN

    @websocket_retry
    async def connect(self) -> None:
        """Establish a WebSocket connection to the Inworld Realtime API.

        Raises:
            RuntimeError: If the initial handshake fails.
        """
        if self.is_connected:
            return

        headers = {"Authorization": f"Basic {self.api_key}"}
        url = (
            f"{self.BASE_URL}"
            f"?key=voice-{int(time.time() * 1000)}"
            f"&protocol=realtime"
        )

        logger.info(f"Inworld Realtime API: Connecting to {self.BASE_URL}")
        self.ws = await websockets.connect(url, additional_headers=headers)

        # Wait for session.created event
        response = await self.ws.recv()
        data = json.loads(response)
        if data.get("type") != "session.created":
            raise RuntimeError(
                f"Expected session.created, got {data.get('type')}"
            )

        session = data.get("session", {})
        self.session_id = session.get("id") or data.get("event_id")
        logger.info(
            f"Inworld Realtime API: Connected (session_id={self.session_id})"
        )

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self.ws:
            logger.info("Inworld Realtime API: Disconnecting")
            await self.ws.close()
            self.ws = None
            logger.info("Inworld Realtime API: Disconnected")

    def _format_tools_for_api(self, tools: List[Tool]) -> List[Dict]:
        """Format tools for the Inworld API (OpenAI-compatible schema)."""
        formatted_tools = []
        for tool in tools:
            schema = tool.openai_schema
            formatted_tools.append(
                {
                    "type": "function",
                    "name": schema["function"]["name"],
                    "description": schema["function"]["description"],
                    "parameters": schema["function"]["parameters"],
                }
            )
        return formatted_tools

    def _build_turn_detection_config(self, vad_config: InworldVADConfig) -> Dict:
        """Build the semantic VAD turn-detection config."""
        return {
            "type": "semantic_vad",
            "eagerness": vad_config.eagerness.value
            if hasattr(vad_config.eagerness, "value")
            else vad_config.eagerness,
            "create_response": vad_config.create_response,
            "interrupt_response": vad_config.interrupt_response,
        }

    async def configure_session(
        self,
        system_prompt: str,
        tools: List[Tool],
        vad_config: InworldVADConfig,
        modality: str = "audio",
    ) -> None:
        """Configure the realtime session with instructions, tools, and audio.

        Args:
            system_prompt: The system instructions for the assistant.
            tools: List of tools available for the assistant to use.
            vad_config: Voice Activity Detection configuration.
            modality: "audio" or "text" (Inworld only supports audio in practice).

        Raises:
            RuntimeError: If not connected or if session configuration fails.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to API. Call connect() first.")

        if modality == "audio":
            output_modalities = ["audio"]
        elif modality == "text":
            output_modalities = ["text"]
        else:
            output_modalities = ["audio"]

        input_config: Dict = {
            "format": {
                "type": "audio/pcm",
                "rate": self.sample_rate,
            },
            "turn_detection": self._build_turn_detection_config(vad_config),
        }
        # Optional in-session STT model + language hint. Omit either field if
        # the constructor and env both left it unset so we don't send empty
        # strings that some upstream models may reject.
        if self.realtime_stt_model or self.realtime_stt_language:
            transcription: Dict = {}
            if self.realtime_stt_model:
                transcription["model"] = self.realtime_stt_model
            if self.realtime_stt_language:
                transcription["language"] = self.realtime_stt_language
            input_config["transcription"] = transcription

        session_config = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.model,
                "instructions": system_prompt,
                "output_modalities": output_modalities,
                "audio": {
                    "input": input_config,
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self.sample_rate,
                        },
                        "model": self.tts_model,
                        "voice": self.voice,
                    },
                },
                "tools": self._format_tools_for_api(tools),
            },
        }

        logger.debug(
            f"Inworld session config: {json.dumps(session_config, indent=2)}"
        )
        await self.ws.send(json.dumps(session_config))

        while True:
            response = await self.ws.recv()
            data = json.loads(response)
            event_type = data.get("type", "")
            if event_type == "session.updated":
                self._current_vad_config = vad_config
                # Stash the args so we can replay configure_session on a
                # mid-run reconnect. Stash after we've confirmed success so we
                # don't cache a known-bad config.
                self._session_config_cache = {
                    "system_prompt": system_prompt,
                    "tools": tools,
                    "vad_config": vad_config,
                    "modality": modality,
                }
                logger.info("Inworld Realtime API: Session configured")
                return
            if event_type == "error":
                error = data.get("error", {})
                error_msg = error.get("message", str(error))
                raise RuntimeError(f"Session configuration failed: {error_msg}")

    async def _ensure_connected(self) -> None:
        """Reconnect + replay the session config if the websocket has dropped.

        Called by send_audio / cancel_response / send_tool_result / receive_events
        before they touch ``self.ws``. Idempotent and single-flight (multiple
        concurrent coroutines that observe the disconnect coordinate via the
        reconnect lock so we don't fan out N parallel reconnect attempts).

        Raises ``RuntimeError`` if we've exhausted ``_max_reconnect_attempts``
        — at that point the caller should abandon the task. A permanently
        failed provider is preferable to a silent infinite loop.
        """
        if self.is_connected:
            return
        if self._session_config_cache is None:
            # Pre-configure_session disconnect — no state to replay, just bubble.
            raise RuntimeError("Not connected to API")

        if self._reconnect_lock is None:
            self._reconnect_lock = asyncio.Lock()

        async with self._reconnect_lock:
            # Re-check inside the lock; a peer coroutine may have already healed.
            if self.is_connected:
                return
            if self._reconnect_failures >= self._max_reconnect_attempts:
                raise RuntimeError(
                    f"Inworld Realtime API: giving up after "
                    f"{self._reconnect_failures} reconnect attempts"
                )

            attempt = self._reconnect_failures + 1
            logger.warning(
                f"Inworld Realtime API: websocket dropped, attempting "
                f"reconnect ({attempt}/{self._max_reconnect_attempts})"
            )
            try:
                # Force a fresh connection — drop any half-closed socket first
                # so connect() doesn't short-circuit on a stale handle.
                self.ws = None
                await self.connect()
                cache = self._session_config_cache
                await self.configure_session(
                    system_prompt=cache["system_prompt"],
                    tools=cache["tools"],
                    vad_config=cache["vad_config"],
                    modality=cache["modality"],
                )
            except Exception as e:
                self._reconnect_failures += 1
                logger.error(
                    f"Inworld Realtime API: reconnect attempt {attempt} "
                    f"failed: {type(e).__name__}: {e}"
                )
                raise
            # Reset failure count on a clean reconnect so a single drop
            # doesn't poison subsequent runs of the same task.
            self._reconnect_failures = 0
            logger.info("Inworld Realtime API: reconnect + session replay OK")

    async def send_audio(self, audio_data: bytes) -> None:
        """Append PCM16 audio bytes to the input audio buffer (base64-encoded)."""
        await self._ensure_connected()
        audio_b64 = base64.b64encode(audio_data).decode("utf-8")
        try:
            await self.ws.send(
                json.dumps({"type": "input_audio_buffer.append", "audio": audio_b64})
            )
        except websockets.ConnectionClosed:
            # The drop landed between _ensure_connected() and send. Heal and
            # try once more — if that fails, let it propagate.
            await self._ensure_connected()
            await self.ws.send(
                json.dumps({"type": "input_audio_buffer.append", "audio": audio_b64})
            )

    async def cancel_response(self) -> None:
        """Cancel the in-flight assistant response (used for barge-in)."""
        if not self.is_connected:
            return
        try:
            await self.ws.send(json.dumps({"type": "response.cancel"}))
        except websockets.ConnectionClosed:
            # Cancellation is best-effort; if the socket is gone the in-flight
            # response is gone with it. Don't surface an error to the caller.
            logger.debug("Inworld Realtime API: cancel_response on closed ws")

    async def send_tool_result(
        self, call_id: str, result: str, request_response: bool = True
    ) -> None:
        """Send a tool result and optionally request a continuation."""
        await self._ensure_connected()

        item_create = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            },
        }
        await self.ws.send(json.dumps(item_create))

        if request_response:
            await self.ws.send(json.dumps({"type": "response.create"}))

    async def receive_events(self) -> AsyncGenerator[BaseInworldEvent, None]:
        """Receive and yield events from the WebSocket connection.

        Auto-heals a mid-session disconnect: on ``ConnectionClosed`` we attempt
        a bounded reconnect via :py:meth:`_ensure_connected` and continue the
        loop. If reconnect is exhausted, the underlying ``RuntimeError`` is
        raised so the caller can fail the task instead of looping silently.
        """
        await self._ensure_connected()

        while self.is_connected:
            try:
                raw_message = await asyncio.wait_for(self.ws.recv(), timeout=0.01)
                data = json.loads(raw_message)
                yield parse_inworld_event(data)
            except asyncio.TimeoutError:
                yield InworldTimeoutEvent(type="timeout")
            except websockets.ConnectionClosed as e:
                logger.warning(
                    f"Inworld Realtime API: WebSocket closed mid-receive "
                    f"(code={e.code}, reason='{e.reason or 'no reason'}'); "
                    f"attempting reconnect"
                )
                # Let _ensure_connected handle the bounded retry + replay; if
                # it raises, propagate to the caller (the adapter / orchestrator
                # turns this into a task-level failure, which is preferable to
                # an infinite tick loop on a dead socket).
                await self._ensure_connected()
                yield InworldTimeoutEvent(type="timeout")
            except Exception as e:
                logger.error(f"Inworld Realtime API: Error receiving event: {e}")
                yield InworldUnknownEvent(type="error", raw={"error": str(e)})

    async def receive_events_for_duration(
        self, duration_seconds: float
    ) -> List[BaseInworldEvent]:
        """Receive events for the specified duration (tick-based polling)."""
        events: List[BaseInworldEvent] = []
        end_time = asyncio.get_event_loop().time() + duration_seconds

        async for event in self.receive_events():
            if not isinstance(event, InworldTimeoutEvent):
                events.append(event)
            if asyncio.get_event_loop().time() >= end_time:
                break
        return events
