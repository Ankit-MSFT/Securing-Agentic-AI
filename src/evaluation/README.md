# Evaluation harness

This directory will hold the code that runs the experiment and computes security outcomes.

## Planned responsibilities

- launch baseline and hardened agents
- execute scenario-specific attack runs
- collect logs and tool traces
- compute ASR and secondary metrics
- aggregate findings for comparison and reporting

## Key metric

Attack Success Rate = successful attacks / total attack attempts

The evaluation layer should remain separate from both the domain code and the agent implementations so results are traceable and reproducible.
