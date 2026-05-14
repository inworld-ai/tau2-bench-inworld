# Fork notes — tau2-bench-inworld

This repository is an Inworld AI fork of [tau2-bench](https://github.com/sierra-research/tau2-bench)
(MIT-licensed, © Sierra Research). The goal of the fork is to make the benchmark
runnable end-to-end with **only an `INWORLD_API_KEY` set** — no separate OpenAI,
Anthropic, ElevenLabs, or Deepgram keys required.

This document is meant to make the diff auditable for anyone reading the public
repo.

## What changed

### LLM routing — text + judge (Steps 2)
All `litellm.completion(...)` calls now recognize an `inworld/` model prefix
and route through the Inworld LLM Router (`https://api.inworld.ai/v1`, an
OpenAI-compatible endpoint with `Authorization: Basic <key>`). The Inworld
prefix is stripped and the remainder of the model string is forwarded
verbatim, so `inworld/openai/gpt-4.1-mini` and `inworld/anthropic/claude-sonnet-4-6`
both work over a single endpoint.

Default models flipped to Inworld-routed equivalents:

| Role                          | Was                          | Now                                   |
|-------------------------------|------------------------------|---------------------------------------|
| Agent                         | `gpt-4.1-2025-04-14`         | `inworld/anthropic/claude-sonnet-4-6` |
| User simulator                | `gpt-4.1-2025-04-14`         | `inworld/openai/gpt-4.1-mini`         |
| NL assertions                 | `gpt-4.1-2025-04-14`         | `inworld/anthropic/claude-sonnet-4-6` |
| Env-interface tooling         | `gpt-4.1-2025-04-14`         | `inworld/openai/gpt-4.1-mini`         |
| Judge (eval user simulator)   | `claude-opus-4-5`            | `inworld/anthropic/claude-opus-4-7`   |
| Voice user-simulator decisions| `gpt-4.1`                    | `inworld/openai/gpt-4.1`              |

Touched files: `src/tau2/utils/llm_utils.py`, `src/tau2/config.py`.

### Text-to-speech — user simulator audio (Step 3)
Added an Inworld TTS backend (`src/tau2/voice/utils/inworld_utils.py`,
`InworldTTSConfig` in `src/tau2/data_model/voice.py`) that calls
`POST https://api.inworld.ai/tts/v1/voice` and decodes the WAV/LINEAR16
response into PCM_S16LE.

Each user persona now ships with an `inworld_voice_id` chosen to match the
persona's accent (see `docs/voice-personas.md`). `DEFAULT_VOICE_SYNTHESIS_PROVIDER`
flipped from `elevenlabs` to `inworld`. ElevenLabs remains supported as an
opt-in backend; its SDK is imported lazily so a missing `elevenlabs` install
isn't fatal.

Touched files: `src/tau2/voice/synthesis/synthesize.py`,
`src/tau2/voice/utils/inworld_utils.py`, `src/tau2/data_model/voice.py`,
`src/tau2/data_model/voice_personas.py`, `src/tau2/voice_config.py`,
`src/tau2/agent/base/voice.py`,
`src/tau2/voice/synthesis/audio_effects/speech_generator.py`.

### Speech-to-text — agent audio (Step 4)
Added an Inworld STT backend (`src/tau2/voice/transcription/inworld_stt.py`)
that calls `POST https://api.inworld.ai/stt/v1/transcribe` with a WAV-wrapped
PCM16 payload. `DEFAULT_TRANSCRIPTION_MODEL` flipped from `nova-3` (Deepgram)
to `inworld-stt`. Deepgram and OpenAI Whisper paths remain available for
users who still want them.

Touched files: `src/tau2/voice/transcription/inworld_stt.py`,
`src/tau2/voice/transcription/transcribe.py`, `src/tau2/data_model/voice.py`,
`src/tau2/voice_config.py`.

### Persona → voice mapping (Step 3)
Picked from the live Inworld TTS catalog. Non-English personas use voices
whose native language matches the persona's L1, so the cross-lingual accent
shape lands close to the persona description.

| Persona         | Accent target          | Inworld voice | Notes                                  |
|-----------------|------------------------|---------------|----------------------------------------|
| MATT_DELANEY    | American Midwest       | `Dennis`      | calm, friendly male                    |
| LISA_BRENNER    | Suburban American      | `Bianca`      | controlled, measured authority         |
| MILDRED_KAPLAN  | Elderly American       | `Deborah`     | warm, peaceful tone                    |
| ARJUN_ROY       | Bengali-English        | `Arjun`       | Indian male, instructional             |
| WEI_LIN         | Sichuan Mandarin       | `Jing`        | zh native voice, cross-lingual         |
| MAMADOU_DIALLO  | Senegalese L1-French   | `Étienne`     | fr native voice, cross-lingual         |
| PRIYA_PATIL     | Maharashtrian          | `Priya`       | Indian female                          |

All seven voices have `isCustom: false`, so they are available to any
`INWORLD_API_KEY` holder out of the box. `TAU2_VOICE_ID_<NAME>` env-var
overrides remain in place for substituting custom voices.

### Realtime auto-reconnect (post-initial fork)
`InworldRealtimeProvider.send_audio` previously raised `RuntimeError("Not connected
to API")` and gave up the moment the websocket dropped, which during an overnight
50-task run translated to silent multi-hour stalls on the last two in-flight tasks.
The provider now:

- Caches the `configure_session(...)` arguments after the first successful session.
- Exposes `_ensure_connected()` that, on a closed socket, single-flights a reconnect
  (lock-protected against the receive coroutine racing the send coroutine), replays
  the cached session config, and returns.
- Caps reconnect attempts at 3, then raises so the orchestrator surfaces a task-level
  failure instead of looping silently.
- `send_audio` / `cancel_response` / `send_tool_result` / `receive_events` all call
  `_ensure_connected()` before touching `self.ws`.

Touched files: `src/tau2/voice/audio_native/inworld/provider.py`.

### TTS sample-rate + model parity (post-initial fork)
Two bugs on the user-simulator TTS path:

- `InworldTTSConfig` defaulted to **24 kHz** but the user-sim streaming pipeline
  hard-codes `PCM_SAMPLE_RATE = 16000` and plays raw PCM at that rate without
  resampling from `AudioData.format.sample_rate`. Net effect: audio played at
  0.667× speed, low-pitched and confusing both sides of the conversation
  (manifested as elevated "Unresponsive Period" counts and Max-Steps timeouts).
- `InworldTTSConfig` defaulted to **`inworld-tts-1.5-mini`** while the realtime
  agent side used **`inworld-tts-2`** — the two sides of the conversation were
  on different TTS engines.

Both defaults flipped (`inworld-tts-2` @ 16 kHz). Smoke-tested 3-task airline run
went from 0.67 → 1.00 avg reward and 20% → 0% unresponsive after the fix.

Touched files: `src/tau2/data_model/voice.py`.

### Save-path normalization + timestamp-first naming (post-initial fork)
`--save-to data/simulations/foo.json` previously double-nested as
`data/simulations/data/simulations/foo.json/results.json` because the runner
unconditionally prepends `DATA_DIR / "simulations" / save_to`. The runner now
strips any `data/simulations/` or `simulations/` prefix, takes only the leaf path
component, drops a trailing `.json`, and always prepends a timestamp — so the
final directory is `data/simulations/<YYYYMMDD_HHMMSS>_<tag>/` regardless of
what the user passes. Matches the upstream auto-generated `make_run_name`
format so `ls -t` sorts chronologically.

Touched files: `src/tau2/runner/batch.py`.

### Eagerness wiring (post-initial fork)
`DEFAULT_INWORLD_EAGERNESS` existed in `config.py` but `InworldVADConfig.eagerness`
was a hardcoded `InworldEagerness.HIGH` literal in the provider — they weren't
connected. Wired the pydantic default to read the config constant, then flipped
the constant from `high` to `low` (lower-eagerness VAD waits longer before
declaring end-of-turn, fewer mid-utterance interruptions). A/B-tested
3-task airline run: 0.67 → 1.00 avg reward at LOW vs HIGH with all other
settings constant.

Touched files: `src/tau2/voice/audio_native/inworld/provider.py`,
`src/tau2/config.py`.

### Default-model bumps (post-initial fork)
After running a series of voice evals on airline+telecom, the validated stack is:

| Constant | Value | Where |
|----------|-------|-------|
| `DEFAULT_LLM_USER`                    | `inworld/openai/gpt-5.4-mini` | `config.py` |
| `VOICE_USER_SIMULATOR_DECISION_MODEL` | `inworld/openai/gpt-5.4-mini` | `config.py` |
| `DEFAULT_INWORLD_MODEL` (realtime LLM)| `openai/gpt-5.4-mini`         | `config.py` |
| `DEFAULT_INWORLD_TTS_MODEL`           | `inworld-tts-2`               | `config.py` |
| `DEFAULT_INWORLD_TTS_MODEL_ID` (text) | `inworld-tts-2`               | `data_model/voice.py` |
| `DEFAULT_INWORLD_VOICE`               | `Jason`                       | `config.py` |
| `DEFAULT_INWORLD_EAGERNESS`           | `low`                         | `config.py` |
| `DEFAULT_INWORLD_TTS_SAMPLE_RATE`     | `16000`                       | `data_model/voice.py` |
| `DEFAULT_MAX_STEPS_SECONDS`           | `300`                         | `config.py` |

Text-mode agent + judge stay on Claude (`claude-sonnet-4-6` / `claude-opus-4-7`)
since those paths aren't exercised by the voice runs and Claude is a strong
default for text tool-use.

### Wall-clock watchdog for audio-native runs (post-initial fork)
Each tau2 task has a simulated-time cap (`--max-steps-seconds`, defaulting to
300s), but if the orchestrator's tick loop fails to advance the simulated clock
(both sides silent, audio plumbing hang, etc.) the loop can wall-clock forever.
The base `Orchestrator` already had a `_check_timeout()` that uses
`time.perf_counter()` against a `timeout` constructor arg, but the CLI
defaulted that arg to `None`. We now default it to `2 × max_steps_seconds`
whenever `--audio-native` is set, so a single stuck simulation can't starve
the whole batch. Explicit `--timeout` still wins; text-mode runs are
unaffected.

Touched files: `src/tau2/cli.py`.

### Evaluator hardening (post-initial fork)
A 40-task retail voice eval was killed mid-run because two tasks burned 10,000s
and 15,727s of wall-clock each. Root cause turned out to be **after** the
orchestrator returned, not inside it: `evaluator_nl_assertions.py:127` did a
bare `json.loads()` on the eval LLM's response, and on very long voice
transcripts the Inworld-routed `claude-sonnet-4-6` was returning empty content,
crashing the parse. The exception propagated up to the runner's 4-attempt
retry loop, and each retry called `generate()` → `litellm.completion()` with
`num_retries=3` and **no `timeout`** — so a single hung LLM call could wait
hours, multiplied by every retry. Three concurrent workers all stuck in I/O.

Three coordinated fixes:

1. **Defensive parse** — `evaluator_nl_assertions.py` now wraps the
   `json.loads()` in a try/except via the existing
   `extract_json_from_llm_response()` helper. On failure, the function returns
   `met=False` with a `eval_parse_failed:<exc>` justification for each
   assertion instead of crashing the whole task.
2. **Per-call timeout** — every `generate()` invocation in the evaluator /
   reviewer / auth-classifier paths now passes
   `timeout=DEFAULT_LLM_EVAL_TIMEOUT_SECONDS` (=120s, new constant in
   `config.py`). Worst case per eval call: 3 retries × 120s = 360s, vs.
   unbounded previously.
3. **Model swap for NL assertions** — `DEFAULT_LLM_NL_ASSERTIONS` moved from
   `inworld/anthropic/claude-sonnet-4-6` to `inworld/openai/gpt-5.4-mini`. The
   empty-content artifact correlated with very long retail transcripts + that
   specific routed model; gpt-5.4-mini also matches what we use for the agent
   and user simulator so the eval and the participants share a model family.

Together these three eliminate the "one stuck task starves the batch for
hours" failure mode. The wall-clock watchdog above is the last-resort safety
net; these fixes prevent the runaway from happening in the first place.

Touched files: `src/tau2/config.py`,
`src/tau2/evaluator/evaluator_nl_assertions.py`,
`src/tau2/evaluator/auth_classifier.py`,
`src/tau2/evaluator/hallucination_reviewer.py`,
`src/tau2/evaluator/review_llm_judge.py`,
`src/tau2/evaluator/review_llm_judge_user_only.py`.

### Env / docs / metadata (Step 5)
- `.env.example` collapsed to a single required key (`INWORLD_API_KEY`) at
  the top, with the legacy provider keys moved to a clearly-marked
  "Optional / legacy" section.
- `README.md` rewritten with an Inworld-first quick start and explicit
  attribution to upstream tau2-bench.
- `LICENSE` keeps upstream MIT verbatim; a second copyright line attributes
  the fork to Inworld AI.
- `pyproject.toml`: distribution name renamed to `tau2-bench-inworld`. The
  import package name remains `tau2` so existing scripts/imports keep
  working; the `tau2` CLI entry point is unchanged. Added a
  `[tool.hatch.build.targets.wheel]` section so hatchling can find
  `src/tau2/` despite the dist-name change.
- `docs/voice-personas.md` rewritten to point at the Inworld voice catalog
  and the persona mapping above.

## What was deliberately left unchanged

- `src/tau2/voice/audio_native/inworld/` — the existing realtime agent
  provider is already production-ready; no edits were needed.
- `src/tau2/agent/llm_agent.py`, `src/tau2/user/user_simulator.py`,
  `src/tau2/evaluator/review_llm_judge.py` — they read defaults from
  `config.py`, so flipping the defaults was enough.
- Domain task definitions under `src/tau2/domains/` and `data/tau2/` —
  model-agnostic.
- The ElevenLabs / Deepgram / OpenAI backends remain available as opt-in
  alternatives; they are imported lazily and gated on their own env vars.

## Upstream relationship

This fork started from tau2-bench at the commit checked out in
`/Users/cale/code/tau2-bench/` on the day of the fork (2026-05-12). It
inherits all task definitions, agent/user/judge harness code, voice-effects
pipeline, and CLI from upstream — only the *provider plumbing* changed.

Bug reports against the benchmark methodology should generally still go to
[sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench).
Issues specific to the Inworld routing layer (LLM router, Inworld TTS,
Inworld STT, persona voice mapping) belong here.
