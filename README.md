# tau2-bench-inworld

> **A port of [tau2-bench](https://github.com/sierra-research/tau2-bench) that uses
> [Inworld](https://inworld.ai/) for LLM, TTS, STT, and full-duplex realtime by default.**
>
> Run the full tool-agent-user benchmark — text and voice — with **only `INWORLD_API_KEY` set**.
> The original tau2-bench providers (OpenAI, Anthropic, ElevenLabs, Deepgram, Gemini Live,
> xAI Realtime, etc.) remain supported as drop-in alternatives; the Inworld backends are
> additive defaults, not replacements. See [FORK_NOTES.md](FORK_NOTES.md) for the full
> diff vs. upstream.

[![python](https://img.shields.io/badge/Python-3.12%2B-blue.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![arXiv](https://img.shields.io/badge/cs.AI-arXiv%3A2506.07982-B31B1B.svg?logo=arxiv&logoColor=red)](https://arxiv.org/abs/2506.07982)
[![Upstream](https://img.shields.io/badge/upstream-tau2--bench-blue)](https://github.com/sierra-research/tau2-bench)

<div align="center">
<img src="figs/traj.png" width="95%" alt="Trajectory">
</div>

<div align="center">
<h3>🚀 τ³-bench is here!</h3>
<p>From text-only to multimodal, knowledge-aware agent evaluation.<br>
Voice full-duplex · Knowledge retrieval · 75+ task fixes<br>
<a href="https://arxiv.org/abs/2603.13686">τ-Voice paper</a> · <a href="https://arxiv.org/abs/2603.04370">τ-Knowledge paper</a> · <a href="https://arxiv.org/abs/2512.07850">Task fixes paper</a> · <a href="https://github.com/sierra-research/tau2-bench/releases/tag/v1.0.0">Release notes</a></p>
</div>

> **How do you say $\tau^3$-bench?** We just say "tau three," but you do you!

## What's New in $\tau^3$-bench

- **Knowledge Domain (`banking_knowledge`)** — A knowledge-retrieval-based customer service domain with configurable RAG pipelines, document search, embeddings, and agentic shell-based search. [Learn more →](src/tau2/knowledge/README.md)
- **Voice Full-Duplex (Audio Native)** — End-to-end voice evaluation with realtime providers (OpenAI, Gemini, xAI). [Learn more →](src/tau2/voice/README.md)
- **Task Quality (75+ fixes)** — Removed incorrect expected actions, clarified ambiguous instructions, fixed impossible constraints, and added missing fallback behaviors across airline, retail, and banking domains. Based on analysis from [SABER](https://arxiv.org/abs/2512.07850) (Cuadron et al., 2025). [Learn more →](https://taubench.com/blog/tau3-task-fixes.html)

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

> **Backward compatibility note**: If you are evaluating an agent (not training), use the `base` task split to evaluate on the complete task set that matches the original τ-bench structure. This is the default.

> **Upgrading from $\tau^2$-bench?** Installation now uses `uv` instead of `pip install -e .`, and Python `>=3.12, <3.14` is required (was `>=3.10`). Some internal APIs have been refactored — see [CHANGELOG.md](CHANGELOG.md) for details.

## Overview

$\tau$-bench is a simulation framework for evaluating customer service agents across multiple domains. It supports text-based half-duplex (turn-based) evaluation and voice full-duplex (simultaneous) evaluation using real-time audio APIs.

Each domain specifies:
- A **policy** that the agent must follow
- A set of **tools** that the agent can use
- A set of **tasks** to evaluate the agent's performance
- Optionally: a set of **user tools** for the user simulator

**Available domains**: `mock` · `airline` · `retail` · `telecom` · `banking_knowledge`

| Mode | Description | Default provider |
|------|-------------|------------------|
| **Text (half-duplex)** | Turn-based chat with tool use | Inworld LLM Router |
| **Voice (full-duplex)** | End-to-end audio via a realtime API | Inworld Realtime |

Other realtime providers (OpenAI, Gemini Live, xAI, AWS Nova Sonic, Qwen-Omni, LiveKit
cascaded) and other LLM/TTS/STT backends (Anthropic, ElevenLabs, Deepgram, Whisper) are
still wired in — pick them with `--audio-native-provider` / model flags and supply the
matching API key. See [FORK_NOTES.md](FORK_NOTES.md) and [`.env.example`](.env.example).

## Quick Start (Inworld-only)

### 1. Install

```bash
git clone https://github.com/inworld-ai/tau2-bench-inworld
cd tau2-bench-inworld
uv sync                        # core (text-mode: airline, retail, telecom, mock)
uv sync --extra voice          # + voice/audio-native features
```

This requires [uv](https://docs.astral.sh/uv/getting-started/installation/).
Voice features also need system dependencies (`brew install portaudio ffmpeg`
on macOS).

### 2. Get an `INWORLD_API_KEY`

1. Sign in at <https://platform.inworld.ai/>.
2. Go to **Profile → API keys** and create a new key.
3. Copy the key (already base64-encoded — paste it verbatim) into `.env`:

```bash
cp .env.example .env
# Then edit .env and set INWORLD_API_KEY=<your_key>
```

You can also paste it inline:

```bash
export INWORLD_API_KEY=<your_key>
```

That's the only required key. The defaults (agent, user simulator, judge, TTS,
STT, full-duplex audio) all route through Inworld.

### 3. Run an evaluation

Text mode:

```bash
tau2 run --domain mock --num-tasks 1
```

Voice (full-duplex) mode:

```bash
tau2 run --domain airline --audio-native --audio-native-provider inworld \
  --num-tasks 3 --speech-complexity regular
```

Results are saved under `data/simulations/<YYYYMMDD_HHMMSS>_<tag>/`. Use `tau2 view` to browse them.

### Defaults

The default voice-eval stack (no flags required beyond `--audio-native --audio-native-provider inworld`):

| Role | Default | Constant |
|------|---------|----------|
| Realtime LLM backbone | `openai/gpt-5.4-mini` | `DEFAULT_INWORLD_MODEL` |
| Realtime TTS engine | `inworld-tts-2` | `DEFAULT_INWORLD_TTS_MODEL` |
| Realtime voice | `Jason` | `DEFAULT_INWORLD_VOICE` |
| Semantic VAD eagerness | `low` | `DEFAULT_INWORLD_EAGERNESS` |
| In-session realtime STT | `soniox/stt-rt-v4` (`en`) | `DEFAULT_INWORLD_REALTIME_STT_MODEL` / `_LANGUAGE` |
| User-sim LLM (decisions) | `inworld/openai/gpt-5.4-mini` | `DEFAULT_LLM_USER` |
| User-sim TTS | `inworld-tts-2` @ 16kHz | `DEFAULT_INWORLD_TTS_MODEL_ID` |
| Post-hoc agent-side STT | `inworld-stt` (= `inworld/inworld-stt-1`) | `DEFAULT_TRANSCRIPTION_MODEL` |
| Text-mode agent | `inworld/anthropic/claude-sonnet-4-6` | `DEFAULT_LLM_AGENT` |
| Text-mode user-sim | `inworld/openai/gpt-5.4-mini` | `DEFAULT_LLM_USER` |
| NL-assertions evaluator | `inworld/openai/gpt-5.4-mini` | `DEFAULT_LLM_NL_ASSERTIONS` |
| Judge (LLM review) | `inworld/anthropic/claude-opus-4-7` | `DEFAULT_LLM_EVAL_USER_SIMULATOR` |
| Max simulated duration | 300s | `DEFAULT_MAX_STEPS_SECONDS` |
| Wall-clock watchdog (voice) | `2 × max-steps-seconds` (default 600s) | CLI default when `--audio-native` and `--timeout` unset |
| Per-call eval LLM timeout | 120s | `DEFAULT_LLM_EVAL_TIMEOUT_SECONDS` |

### Customizing models

Every default model uses the `inworld/` prefix so it routes through the Inworld
LLM Router. To swap any of them, pass a different Inworld-routed name:

```bash
tau2 run --domain mock \
  --agent-llm inworld/anthropic/claude-opus-4-7 \
  --user-llm inworld/openai/gpt-4.1-mini \
  --num-tasks 1
```

To run against the original upstream providers instead, drop the `inworld/`
prefix and set the matching key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY`). All the original tau2-bench backends
— ElevenLabs TTS, Deepgram/OpenAI STT, OpenAI/Gemini/xAI/Nova/Qwen realtime — are
still wired up; see [`.env.example`](.env.example) and [FORK_NOTES.md](FORK_NOTES.md).

> **Tip**: Run `tau2 intro` for an overview of available domains, commands, and examples.

## Documentation

### Getting Started

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, API keys, first run, output structure, configuration |
| [CLI Reference](docs/cli-reference.md) | All `tau2` commands and options |

### Core Concepts

| Document | Description |
|----------|-------------|
| [Agent Developer Guide](src/tau2/agent/README.md) | Build and evaluate your own agent |
| [Domains](src/tau2/domains/README.md) | Domain structure, data format, and available domains |
| [Orchestrator & Communication Modes](src/tau2/orchestrator/README.md) | Half-duplex and full-duplex orchestration |

### Knowledge Retrieval

| Document | Description |
|----------|-------------|
| [Knowledge Retrieval](src/tau2/knowledge/README.md) | Retrieval pipeline configs, embeddings, RAG, and sandbox setup for the `banking_knowledge` domain |

### Voice & Audio

| Document | Description |
|----------|-------------|
| [Voice (Full-Duplex)](src/tau2/voice/README.md) | Providers, speech complexity, CLI options, and output structure for voice evaluation |
| [Audio Native Architecture](src/tau2/voice/audio_native/README.md) | Internal architecture for adding or modifying realtime provider adapters |

### RL & Training

| Document | Description |
|----------|-------------|
| [Gym Interface](src/tau2/gym/README.md) | Gymnasium-compatible environment, play mode, train/test splits |

### Experiments

| Document | Description |
|----------|-------------|
| [Experiments](src/experiments/README.md) | Experimental features and research code |

### Project

| Document | Description |
|----------|-------------|
| [Contributing](CONTRIBUTING.md) | How to contribute to τ-bench |
| [Changelog](CHANGELOG.md) | Version history and release notes |

## Contributing

We welcome contributions! Whether you're fixing bugs, adding features, creating domains, or contributing research code, see our [Contributing Guide](CONTRIBUTING.md) for guidelines.

## Citation

If you use a specific component of $\tau^3$-bench, please cite the corresponding paper below.

### Knowledge Domain (`banking_knowledge`)

```bibtex
@article{shi2026tau,
  title={$\tau$-Knowledge: Evaluating Conversational Agents over Unstructured Knowledge},
  author={Shi, Quan and Zytek, Alexandra and Razavi, Pedram and Narasimhan, Karthik and Barres, Victor},
  journal={arXiv preprint arXiv:2603.04370},
  year={2026}
}
```

### Voice Full-Duplex Benchmark

```bibtex

@misc{ray2026tauvoicebenchmarkingfullduplexvoice,
      title={$\tau$-Voice: Benchmarking Full-Duplex Voice Agents on Real-World Domains},
      author={Soham Ray and Keshav Dhandhania and Victor Barres and Karthik Narasimhan},
      year={2026},
      eprint={2603.13686},
      archivePrefix={arXiv},
      primaryClass={cs.SD},
      url={https://arxiv.org/abs/2603.13686},
}
```

### Core $\tau$-Bench

```bibtex

@misc{barres2025tau2,
      title={$\tau^2$-Bench: Evaluating Conversational Agents in a Dual-Control Environment}, 
      author={Victor Barres and Honghua Dong and Soham Ray and Xujie Si and Karthik Narasimhan},
      year={2025},
      eprint={2506.07982},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2506.07982}, 
}

@misc{yao2024tau,
      title={$\tau$-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains}, 
      author={Shunyu Yao and Noah Shinn and Pedram Razavi and Karthik Narasimhan},
      year={2024},
      eprint={2406.12045},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2406.12045}, 
}
```

### Task Fixes

```bibtex

@inproceedings{cuadron2026saber,
      title={{SABER}: Small Actions, Big Errors {\textemdash} Safeguarding Mutating Steps in {LLM} Agents},
      author={Alejandro Cuadron and Pengfei Yu and Yang Liu and Arpit Gupta},
      booktitle={ICLR 2026 Workshop on Memory for LLM-Based Agentic Systems},
      year={2026},
      url={https://openreview.net/forum?id=En2z9dckgP},
}
```
