# Voice Persona Setup

In this fork, voice personas use [Inworld TTS](https://platform.inworld.ai/)
out of the box. Each persona ships with an `inworld_voice_id` chosen from the
public Inworld voice catalog so the persona's accent and tone are reasonable
without any further setup. As long as you have an `INWORLD_API_KEY` set you
should not have to configure anything else — the default voices will work
immediately.

## Default persona → Inworld voice mapping

| Persona         | Description (from tau2-bench) | Inworld voice  | Voice notes |
|-----------------|-------------------------------|----------------|-------------|
| `matt_delaney`  | Middle-aged Midwestern American male, calm | `Dennis`       | Smooth, calm and friendly male |
| `lisa_brenner`  | Late-40s suburban American woman, tense    | `Bianca`       | Deep, controlled female with measured authority |
| `mildred_kaplan`| Elderly American woman, early 80s          | `Deborah`      | Warm, peaceful female tone |
| `arjun_roy`     | Bengali man, Dhaka, mid-30s, BN-English    | `Arjun`        | Clear, composed Indian male voice |
| `wei_lin`       | Chinese woman, Sichuan, late 20s           | `Jing` (zh)    | Energetic young Chinese female; cross-lingual EN synthesis |
| `mamadou_diallo`| Senegalese L1-French man, mid-30s          | `Étienne` (fr) | Calm young adult French male; cross-lingual EN synthesis |
| `priya_patil`   | Maharashtrian woman, early 30s             | `Priya`        | Even-toned female voice with Indian accent |

All seven voices are non-custom (`isCustom: false` in the Inworld catalog), so
they're available to any `INWORLD_API_KEY` holder. Two of them — `Jing` (zh)
and `Étienne` (fr) — are non-English voices. Inworld TTS supports cross-lingual
synthesis, so English input rendered with these voices preserves the persona's
intended accent shape. If you find the cross-lingual output unsatisfactory, the
closest English-accented fallbacks are `Mei` (zh-flavored EN) for `wei_lin` and
`Mathieu` (fr-flavored EN) for `mamadou_diallo` — set them via the env vars
described below.

## Overriding a voice

To swap any persona's default voice without editing source, set
`TAU2_VOICE_ID_<NAME>` in your environment or `.env`:

```bash
# Replace Matt's voice with another from the Inworld catalog
export TAU2_VOICE_ID_MATT_DELANEY=Edward
```

You can look up available voice IDs by querying the Inworld TTS catalog:

```bash
curl -sS https://api.inworld.ai/tts/v1/voices \
  -H "Authorization: Basic $INWORLD_API_KEY" | jq '.voices[] | {voiceId, languages, description}'
```

Custom-trained voices on your Inworld workspace work the same way — pass their
`voiceId` via the same env var.

## Verifying a persona voice

```bash
INWORLD_API_KEY=<your_key> \
  tau2 run --domain mock --audio-native --audio-native-provider inworld \
  --num-tasks 1 --speech-complexity control
```

Audio for each turn is saved alongside the simulation in
`data/simulations/...artifacts/.../turn_<uuid>/speech.wav`. Listen to a few
turns to confirm the persona sounds correct, then move on to longer runs.

## Legacy ElevenLabs setup

The upstream ElevenLabs flow (ElevenLabs Voice Design, the
`setup_voices` script, etc.) is still available if you prefer it. Each persona
also retains an `elevenlabs_voice_id`. To switch back, set
`DEFAULT_VOICE_SYNTHESIS_PROVIDER = "elevenlabs"` in `src/tau2/voice_config.py`,
make sure `ELEVENLABS_API_KEY` is set, and run `uv sync --extra voice` to pull
in the `elevenlabs` SDK. See the upstream
[tau2-bench voice-personas guide](https://github.com/sierra-research/tau2-bench/blob/main/docs/voice-personas.md)
for the original Voice Design walkthrough.
