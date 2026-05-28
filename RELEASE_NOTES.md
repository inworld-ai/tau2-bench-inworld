> **Note (tau2-bench-inworld fork):** This file is the upstream tau2-bench history. For changes specific to the Inworld fork (LLM router, Inworld TTS/STT, realtime auto-reconnect, save-path normalization, default-model bumps, etc.), see [FORK_NOTES.md](FORK_NOTES.md).

# Release Notes

Welcome to the τ-bench release notes! Here you'll find user-friendly summaries of what's new, what's changed, and what you need to know for each release.

## Version 0.2.1 - Reinforcement Learning Support 🤖

**Release Date**: November 2025

### 🎮 Gymnasium Integration

τ-bench now supports reinforcement learning with a standard Gymnasium-compatible interface!

#### 🌟 What's New
- **Train RL Agents**: Use `AgentGymEnv` and `UserGymEnv` with popular RL frameworks
- **Interactive Play Mode**: New `tau2 play` command lets you control the agent or user manually
- **Train/Test Splits**: Standardized task splits across all domains for proper evaluation
- **Backward Compatible**: Use `base` task split to evaluate on the complete original τ-bench task set
- **Enforce Communication Protocol**: Optionally enforce communication protocol rules (e.g., no mixed messages with text and tool calls)

#### 🚀 Getting Started
```bash
# Try interactive play mode
tau2 play

# Use programmatically with gym interface
from tau2.gym import AgentGymEnv, UserGymEnv
```

See the [Gym Documentation](src/tau2/gym/README.md) for detailed usage examples and API reference.

---

## Version 0.1.3 - Stability & Performance 🔧

**Release Date**: August 26, 2025

### 🐛 Key Fixes

#### LLM Integration Improvements
- **Fixed LLM argument parsing**: Resolved issues with complex LLM configurations
- **Removed problematic assertions**: Eliminated default natural language assertion checks that were causing evaluation failures

#### Impact
These fixes significantly improve the reliability of evaluations, especially when using advanced LLM configurations or custom parameters.

### 🚀 Upgrade Notes
- Simply update to v0.1.3 - no breaking changes
- Existing evaluation configs will work without modification
- Performance should be more consistent across different LLM providers

---

## Version 0.1.2 - Installation & Usability 📦

**Release Date**: July 17, 2025

### 🌟 Installation Made Easy

This release focuses on making τ-bench easier to install and configure for everyone.

#### New Installation Features
- **Default editable install**: `pip install -e .` is now the recommended method
- **Flexible data directory**: Set `TAU2_DATA_DIR` for custom installations
- **Smart fallbacks**: Automatic detection of data directory location
- **Installation verification**: New `tau2 check-data` command

#### Enhanced CLI Experience
```bash
# Verify your installation
tau2 check-data

# Control task count more precisely
tau2 run --domain airline --num-tasks 10 --agent-llm gpt-4
```

#### Developer Experience
- **Better task management**: Improved task name display and filtering
- **Clearer error messages**: More helpful feedback when things go wrong
- **Simplified setup**: Fewer configuration steps required

### 🚀 Migration Guide
If you have an existing installation:
1. Reinstall with `pip install -e .`
2. Run `tau2 check-data` to verify setup
3. Remove any manual data directory configurations (now automatic)

---

## Version 0.1.1 - Quick Fix 🔧

**Release Date**: June 12, 2025

### 🐛 Domain Viewer Fix

Fixed critical issues with the domain documentation viewer:
- `tau2 domain <domain>` now works correctly
- Resolved CLI command execution problems
- Improved error handling for domain-specific operations

---

## Version 0.1.0 - Initial Public Release 🚀

**Release Date**: June 12, 2025

### What is τ-bench?

τ-bench is a comprehensive framework for evaluating conversational agents in realistic, dual-control environments. This groundbreaking release provides everything you need to benchmark your AI agents across multiple customer service domains.

### 🌟 Core Features

#### Multi-Domain Evaluation
- **4 realistic domains**: Mock, Airline, Retail, and Telecom
- Each domain includes realistic policies, tools, and evaluation tasks
- Industry-standard scenarios for comprehensive agent testing

#### Easy-to-Use Command Line Interface
```bash
# Run your first evaluation in minutes
tau2 run --domain airline --agent-llm gpt-4 --user-llm gpt-4 --num-trials 1 --num-tasks 5
```

#### Dual-Control Environment
- **Realistic interactions**: Both agent and user can interact with the system
- **AI-powered user simulation**: Creates authentic conversation scenarios
- **Comprehensive metrics**: Pass@k success rates and detailed performance analysis

### 🔧 For Developers

#### Agent Development Made Simple
- Clean API for implementing custom agents
- Comprehensive documentation for each domain
- Interactive domain viewer at `http://127.0.0.1:8004/redoc`
- Example implementations included

#### Flexible & Extensible
- Support for any LLM provider via LiteLLM
- Configurable concurrency and trial settings
- Redis-based caching for cost optimization
- Extensible domain system for custom scenarios

### 🔬 Research Applications

#### Advanced Evaluation Features
- **Ablation studies**: No-user mode and oracle-plan mode
- **Policy format comparison**: Standard vs workflow policies
- **Comprehensive logging**: Every interaction captured for analysis
- **Statistical rigor**: Multi-trial evaluation with proper metrics

### 🚀 Getting Started

1. **Install**: `pip install -e .`
2. **Configure**: Set up your LLM API keys in `.env`
3. **Run**: `tau2 run --domain mock --agent-llm gpt-4 --user-llm gpt-4 --num-trials 1`
4. **Explore**: `tau2 view` to see your results

### 🤝 Community & Research

- **Paper**: [Read our research paper](https://arxiv.org/abs/2506.07982)
- **Blog**: [Learn more about the methodology](https://sierra.ai/blog/benchmarking-agents-in-collaborative-real-world-scenarios)
- **Open Source**: Full source code available on GitHub
- **Active Development**: Regular updates and community contributions

### ⚠️ Requirements

- **Python 3.10+**: Modern Python version required
- **LLM API Access**: OpenAI, Anthropic, or other LiteLLM-supported providers
- **Optional**: Redis for LLM call caching (disabled by default)

---

*Ready to benchmark your conversational agents? Get started with τ-bench today!*