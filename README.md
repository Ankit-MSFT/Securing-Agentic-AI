# Securing-Agentic-AI

Experimental evaluation of threats and defenses in autonomous AI agents.

> Status: Active research project in progress. The repository follows a layered architecture that separates the bank domain, baseline agent, hardened variants, attacks, and evaluation workflow.

## Objective

This project evaluates whether targeted security controls reduce the Attack Success Rate (ASR) of LangChain-based agents without unnecessarily limiting their autonomy.

The experiment maps attacks and defences to six OWASP Agentic AI threat categories:

| Category | Representative attack | Security control |
|---|---|---|
| Reasoning | Intent breaking | Input/output guardrails |
| Memory | Memory poisoning | Memory integrity validation |
| Execution | Tool misuse | Permission-gated tool authorization |
| Identity | Privilege compromise | Scoped identity tokens |
| Human-Related | Human manipulation | Human-in-the-loop approval |
| Multi-Agent | Agent communication poisoning | Signed inter-agent messages |

## Repository structure

```text
Securing-Agentic-AI/
├── README.md
├── .env                          # shared env (LLM endpoints, MCP overrides)
├── .venv/                        # single virtualenv used by every layer
├── docs/
│   ├── architecture/
│   │   └── midtownbank-hardening-journey.md
│   ├── methodology/workings/
│   ├── references/sources/
│   └── artifacts/
├── src/
│   ├── common/                   # shared config + target abstraction
│   │   ├── config.py             #   load_env, get_llm, bank_mcp_stdio_config
│   │   └── target.py             #   AgentTarget protocol, AgentFactory type
│   ├── bank/                     # domain: models, DB, MCP server, seeder
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── seed.py
│   │   └── mcp_server.py
│   ├── agents/
│   │   ├── baseline/             # intentionally vulnerable agent
│   │   │   ├── factory.py        #   build_agent(model_name)
│   │   │   ├── agent.py          #   CLI entry point
│   │   │   ├── app.py            #   Streamlit UI
│   │   │   └── system_prompt.txt
│   │   └── hardened/steps/       # progressive hardening variants (WIP)
│   ├── attacks/                  # PyRIT target/scorer + scenarios
│   │   ├── pyrit_target.py       #   MidTownAgentTarget(agent_factory=...)
│   │   ├── pyrit_scorer.py
│   │   └── scenario_2a.py
│   ├── controls/                 # reusable security controls (WIP)
│   └── evaluation/               # ASR runner + metrics (WIP)
├── tests/
├── scripts/
├── data/
└── guidelines/
```

## Design principles

- **Domain layer** (`bank`): synthetic bank + MCP server, no knowledge of agents or attacks.
- **Agent layer** (`agents.baseline`, later `agents.hardened.steps.*`): each variant exports a `build_agent()` factory.
- **Attack layer** (`attacks`): drives any agent through an `AgentFactory` — never imports agent internals.
- **Shared layer** (`common`): env loading, LLM factory, MCP launch config, target protocol.
- **Evaluation layer** (`evaluation`): runs scenarios across variants, computes ASR and secondary metrics.

The hardening journey in [docs/architecture/midtownbank-hardening-journey.md](docs/architecture/midtownbank-hardening-journey.md) is treated as a sequence of controls, each landing as its own hardened variant under `src/agents/hardened/steps/`.

## Prerequisites

- Python 3.13 (matches the pinned `.venv`)
- Azure CLI logged in (`az login`) — used for the Foundry token provider
- `.env` at repo root with model endpoints; see `src/agents/baseline/requirements.txt` for the Python deps

## Setup

The repo ships with a working `.venv` at the root. If you need to recreate it:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\activate
pip install -r src\agents\baseline\requirements.txt
```

Then register `src/` as importable (already done in this repo, but needed after a fresh venv):

```powershell
Set-Content .venv\Lib\site-packages\midtown.pth ((Get-Location).Path + "\src")
```

That single `.pth` line replaces the need to `pip install -e .` and lets every layer be imported as `bank`, `common`, `agents.baseline`, `attacks`, etc.

## Running the project

All commands run from the repo root with the venv active.

**Seed the bank database** (once, or whenever you want a fresh state):

```powershell
python -m bank.seed
```

**Run the baseline agent** (CLI):

```powershell
python -m agents.baseline.agent
```

**Run the baseline agent** (Streamlit UI):

```powershell
streamlit run src\agents\baseline\app.py
```

**Run an attack scenario:**

```powershell
python -m attacks.scenario_2a               # normal mode
python -m attacks.scenario_2a --conv        # show attacker/agent conversation
python -m attacks.scenario_2a --debug       # full PyRIT/LLM debug logging
```

## Configuration

`.env` at the repo root is loaded automatically by any entry point via `common.load_env()`.

Relevant variables:

| Variable | Purpose |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure AI Foundry endpoint used by `common.get_llm` |
| `MODEL_GPT` / `MODEL_MISTRAL` / `MODEL_DEEPSEEK` | Deployment names for the three test models |
| `OPENAI_CHAT_ENDPOINT` / `OPENAI_CHAT_KEY` / `OPENAI_CHAT_MODEL` | Used by PyRIT's adversarial/scorer LLMs |
| `MIDTOWN_MCP_COMMAND` | Override the bank MCP launcher (e.g. container image entrypoint) |
| `MIDTOWN_MCP_ARGS` | Override the args passed to the MCP launcher (JSON list) |

The `MIDTOWN_MCP_*` overrides let you move the bank MCP server to Azure Container Apps or another runtime without changing any Python code.

## Current implementation status

- [x] Synthetic MidTownBank environment (`bank`)
- [x] Baseline agent + Streamlit UI (`agents.baseline`)
- [x] Shared config and target abstraction (`common`)
- [x] Scenario 2A (Tool Misuse) attack via PyRIT (`attacks.scenario_2a`)
- [ ] Hardened step variants (`agents.hardened.steps.*`)
- [ ] Attack scenarios 1A, 1B, 2B, 3A, 3B
- [ ] Evaluation runner and metrics (`evaluation`)
- [ ] Regression tests (`tests`)
- [ ] Containerized runtime (Azure Container Apps)

## Next workstreams

1. Move the bank MCP into a container (uses `MIDTOWN_MCP_COMMAND`/`ARGS` — no code change needed).
2. Add hardened agent variants under `src/agents/hardened/steps/`, each exposing its own `build_agent()`.
3. Point `attacks.pyrit_target.MidTownAgentTarget(agent_factory=...)` at each hardened variant to measure ASR reduction.
4. Build the evaluation harness under `src/evaluation/`.
5. Add unit/integration tests under `tests/`.

## References

- [OWASP Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
- [Microsoft PyRIT](https://github.com/Azure/PyRIT)
- [NIST AI 600-1](https://doi.org/10.6028/NIST.AI.600-1)
- [Indirect Prompt Injection Research](https://arxiv.org/abs/2302.12173)

