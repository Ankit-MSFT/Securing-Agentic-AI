# Securing-Agentic-AI

Experimental evaluation of threats and defences in autonomous AI agents.

> **Status:** Work in progress. This repository supports an academic cybersecurity research project and does not yet contain final results.

## Objective

This project evaluates whether targeted security controls reduce the Attack Success Rate (ASR) of LangChain-based agents without unnecessarily limiting their autonomy.

The experiment maps attacks and defences to six OWASP Agentic AI threat categories:

| Category | Representative attack | Security control |
|---|---|---|
| Reasoning | Intent breaking | Input/output guardrails |
| Memory | Memory poisoning | Memory integrity validation |
| Execution | Tool misuse | Permission-gated tool authorization |
| Identity | Privilege compromise | Scoped identity tokens |
| Human-Related | Human manipulation | Human-in-the-Loop approval |
| Multi-Agent | Agent communication poisoning | Signed inter-agent messages |

## Experimental Design

Each scenario is implemented in two states:

1. **Vulnerable:** Deliberately excludes category-specific security controls.
2. **Hardened:** Applies a targeted defence while preserving the same agent architecture.

Both versions are evaluated using identical attack objectives, models, datasets, and execution parameters.

### Scenarios

- **Cognitive:** Reasoning and memory attacks
- **Action and Authority:** Tool execution and identity attacks
- **Interaction:** Human-related and multi-agent attacks

The agents operate in **MidTownBank**, a fictional banking environment containing synthetic customers, accounts, transactions, a mock funds-transfer API, and an isolated MCP toolset.

## Evaluation Matrix

The planned experiment covers:

- 6 OWASP threat categories
- 3 language models
- 2 agent states: vulnerable and hardened
- 30 executions per experimental cell
- **1,080 total attack executions**

Primary measurement:

```text
Attack Success Rate = Successful attacks / Total attack attempts
```

Secondary measurements include:

- ASR reduction after hardening
- Human-in-the-Loop prompts
- Tool authorization refusals
- Benign-task completion rate
- Autonomy and usability trade-offs
- Cross-model differences

## Models

Models are accessed through Azure AI Foundry:

- GPT-4.1-mini
- Llama-3.3-70B-Instruct
- DeepSeek-V4-Flash

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Agent framework | LangChain and LangGraph |
| Model hosting | Azure AI Foundry |
| Red-team harness | Microsoft PyRIT |
| Tool protocol | Model Context Protocol |
| Synthetic data | Faker |
| Data store | SQLite |
| Testing | pytest |
| Containerization | Docker |
| Packaging | `pyproject.toml` |
| Logging | Python logging and PyRIT logs |
| Source control | Git and GitHub |

## Architecture

```text
PyRIT Orchestrator
        |
        v
Attack Objectives and Converters
        |
        v
Vulnerable or Hardened Agent
        |
        +-- LangChain prompts and tools
        +-- LangGraph state and routing
        +-- Memory subsystem
        +-- Identity and authorization
        +-- MCP tools and mock APIs
        |
        v
Azure AI Foundry Model
        |
        v
Deterministic Checker + PyRIT Scorer
        |
        v
Structured Results and ASR Analysis
```

## Security Controls

The hardened agents apply:

- Prompt and response validation
- Memory provenance and integrity checks
- Tool allowlists and permission gates
- Least-privilege identity scopes
- Human approval for sensitive actions
- Signed inter-agent messages
- Structured security-event logging
- Deterministic validation of sensitive operations

## Reproducibility

The experiment uses:

- Fixed random seeds
- Synthetic datasets
- Pinned dependency versions
- Containerized execution
- Resettable SQLite state
- Version-controlled prompts and tools
- Consistent attack objectives
- Structured attack logs
- Deterministic exploit-success checks

## Safety Boundaries

- Testing runs only in isolated local containers.
- Only researcher-owned Azure AI Foundry deployments are targeted.
- No production or third-party systems are tested.
- All customers, accounts, transactions, and messages are synthetic.
- No real personal, financial, or confidential data is used.
- Vulnerable agents exist only for controlled security research.
- Credentials and secrets must never be committed.

## Project Status

- [X] Build the synthetic MidTownBank environment
- [ ] Implement vulnerable agents
- [ ] Implement representative exploits
- [ ] Add category-specific controls
- [ ] Create deterministic exploit checkers
- [ ] Integrate PyRIT orchestration
- [ ] Add unit and benign-task tests
- [ ] Containerize the experiment
- [ ] Execute the evaluation matrix
- [ ] Analyze ASR and autonomy trade-offs
- [ ] Publish final findings

## References

- [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [Microsoft PyRIT](https://github.com/Azure/PyRIT)
- [NIST AI 600-1](https://doi.org/10.6028/NIST.AI.600-1)
- [Indirect Prompt Injection Research](https://arxiv.org/abs/2302.12173)

## Disclaimer

This repository contains an academic experiment under active development. Its implementation, methodology, model selection, and results may change before final submission.
