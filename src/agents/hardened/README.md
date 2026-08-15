# Hardened agent variants

This directory is reserved for the hardened implementation of the MidTownBank assistant.

## Intended progression

The hardened variants should track the security maturity staircase described in the architecture narrative:

1. remote MCP and separated execution boundaries
2. domain-specific tool isolation
3. secret management and identity
4. authorization and least privilege
5. approval gates for sensitive operations
6. tool allowlists and structured policy
7. guardrails, memory integrity, and telemetry
8. governance and evaluation gates

Each step should be implemented as a separate variant or submodule so the project can compare incremental improvements instead of a single monolithic hardening patch.
