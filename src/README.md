# Source code layout

This folder contains the executable implementation for the project.

## Layout

- `bank/`: synthetic bank domain, database, and MCP server
- `agents/`: baseline and hardened agent variants
- `attacks/`: scenario-based attack modules and red-team prompts
- `evaluation/`: execution runner, metrics, and analysis code
- `controls/`: reusable security modules for guardrails, approval, and policy enforcement

## Development guidance

Keep the following boundaries clean:

- Bank code should model the domain, not the research narrative.
- Agent code should handle model orchestration and tool usage.
- Attack code should only test the system under controlled conditions.
- Evaluation code should measure ASR and impact consistently across variants.
