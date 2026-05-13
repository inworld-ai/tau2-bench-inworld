"""Inworld STT backend for tau2-bench.

API contract (verified against ``https://api.inworld.ai/stt/v1/transcribe``):

- Auth: ``Authorization: Basic <INWORLD_API_KEY>`` (key is already base64).
- Body:
  ::

      {
          "audio_data": {"content": <base64-encoded WAV bytes>},
          "transcribe_config": {
              "model_id": "inworld/inworld-stt-1",
              "language": "en-US",
              "audio_encoding": "LINEAR16",
              "sample_rate_hertz": <int>
          }
      }

- Response: ``{"transcription": {"transcript": str, "isFinal": bool, ...}, ...}``.

The endpoint only accepts WAV / MP3 / OGG / FLAC payloads, so we wrap the
incoming raw PCM16 buffer in a WAV header before sending.
"""

import base64
import io
import os
import wave

import requests

from tau2.data_model.audio import AudioData
from tau2.data_model.voice import TranscriptionConfig, TranscriptionResult

INWORLD_STT_URL = "https://api.inworld.ai/stt/v1/transcribe"
INWORLD_STT_MODEL_ID = "inworld/inworld-stt-1"


def _pcm16_to_wav_bytes(audio: AudioData) -> bytes:
    """Wrap raw PCM16 bytes in a WAV container suitable for Inworld STT."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(audio.format.channels)
        wf.setsampwidth(2)
        wf.setframerate(audio.format.sample_rate)
        wf.writeframes(audio.data)
    return buf.getvalue()


def transcribe_inworld(
    audio_data: AudioData, config: TranscriptionConfig
) -> TranscriptionResult:
    """Transcribe PCM_S16LE audio via Inworld STT."""
    api_key = os.getenv("INWORLD_API_KEY")
    if not api_key:
        return TranscriptionResult(
            transcript="", error="INWORLD_API_KEY not found in environment"
        )

    if not audio_data.format.is_pcm16:
        return TranscriptionResult(
            transcript="",
            error=(
                f"Inworld STT expects PCM_S16LE input, got {audio_data.format.encoding}"
            ),
        )

    wav_bytes = _pcm16_to_wav_bytes(audio_data)
    payload = {
        "audio_data": {"content": base64.b64encode(wav_bytes).decode("ascii")},
        "transcribe_config": {
            "model_id": INWORLD_STT_MODEL_ID,
            "language": config.language or "en-US",
            "audio_encoding": "LINEAR16",
            "sample_rate_hertz": audio_data.format.sample_rate,
        },
    }
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            INWORLD_STT_URL, headers=headers, json=payload, timeout=60
        )
        if response.status_code != 200:
            return TranscriptionResult(
                transcript="",
                error=f"Inworld STT error {response.status_code}: {response.text}",
            )
        body = response.json()
    except Exception as e:
        return TranscriptionResult(
            transcript="", error=f"Inworld STT request failed: {e}"
        )

    transcription = body.get("transcription") or {}
    transcript = transcription.get("transcript", "")
    return TranscriptionResult(transcript=transcript)
