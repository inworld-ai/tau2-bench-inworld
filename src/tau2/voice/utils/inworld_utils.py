"""HTTP client for the Inworld TTS REST API.

Inworld TTS exposes two endpoints (this module only wraps the non-streaming
one, which is sufficient for tau2-bench user-side utterances):

- ``POST https://api.inworld.ai/tts/v1/voice`` — returns the entire utterance
  as a single base64-encoded WAV (LINEAR16) payload.

Auth header: ``Authorization: Basic <key>``. The API key is already
base64-encoded — pass it through verbatim.
"""

import io
import os
import wave
from copy import deepcopy

import requests
from loguru import logger

from tau2.data_model.audio import AudioData, AudioEncoding, AudioFormat
from tau2.data_model.voice import InworldTTSConfig

INWORLD_TTS_URL = "https://api.inworld.ai/tts/v1/voice"


def _strip_wav_header(audio_bytes: bytes) -> tuple[bytes, int, int, int]:
    """Decode a WAV container into (raw_pcm_bytes, sample_rate, channels, sample_width).

    Inworld TTS always returns a single WAV (RIFF) blob even when LINEAR16 is
    requested, so we parse off the header and surface the format metadata to
    the caller.
    """
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        raw_pcm = wf.readframes(wf.getnframes())
    return raw_pcm, sample_rate, channels, sample_width


def tts_inworld(text: str, config: InworldTTSConfig) -> AudioData:
    """Text-to-speech via Inworld TTS.

    Returns an :class:`AudioData` with PCM_S16LE audio at the requested sample
    rate (typically 24kHz mono).
    """
    api_key = config.api_key or os.getenv("INWORLD_API_KEY")
    if not api_key:
        raise ValueError("INWORLD_API_KEY not found in config or environment")
    if not config.voice_id:
        raise ValueError("Inworld TTS requires voice_id to be set")

    text_preview = text[:50] + "..." if len(text) > 50 else text
    logger.debug(
        f"Inworld TTS: calling API for text '{text_preview}' "
        f"(voice_id={config.voice_id}, model={config.model_id})"
    )

    payload = {
        "text": text,
        "voiceId": config.voice_id,
        "modelId": config.model_id,
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": config.sample_rate,
        },
    }
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            INWORLD_TTS_URL,
            headers=headers,
            json=payload,
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
    except Exception as e:
        logger.debug(
            f"Inworld TTS API call failed: {type(e).__name__}: {e} "
            f"(text='{text_preview}', voice_id={config.voice_id}, model={config.model_id})"
        )
        raise

    body = response.json()
    audio_content_b64 = body.get("audioContent") or body.get("audio_content")
    if not audio_content_b64:
        raise ValueError(
            f"Inworld TTS response missing audioContent. Body keys: {list(body)}"
        )

    import base64

    audio_bytes = base64.b64decode(audio_content_b64)
    raw_pcm, sample_rate, channels, sample_width = _strip_wav_header(audio_bytes)

    if sample_width != 2:
        raise ValueError(
            f"Inworld TTS returned unexpected sample width {sample_width} bytes "
            "(expected 2 for PCM_S16LE)."
        )

    if len(raw_pcm) == 0:
        raise ValueError(f"Inworld TTS returned empty audio for text: '{text}'")

    audio_format = AudioFormat(
        encoding=AudioEncoding.PCM_S16LE,
        sample_rate=sample_rate,
        channels=channels,
    )
    return AudioData(data=raw_pcm, format=deepcopy(audio_format))
