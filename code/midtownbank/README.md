# MidTownBank — Mock Bank Backend & MCP Server

A fictional bank back-office system used as the testbed for the MCA dissertation
"Security Evaluation of Agentic AI: Three-Scenario Experimental Study".

## Purpose

The MidTown Assistant (LangChain agent) connects to this MCP server to perform
bank operations. The vulnerable version has no guardrails; the hardened version
adds controls per OWASP taxonomy.

## Quick start

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Seed the database (creates midtownbank.db with synthetic data)
python seed.py

# Run the MCP server (stdio transport — agents connect via stdin/stdout)
python mcp_server.py
```

## Structure

| File | Purpose |
|---|---|
| `models.py` | Pydantic data models for all entities |
| `database.py` | SQLite schema creation + CRUD operations |
| `seed.py` | Faker-based synthetic data generation (seed=42, Indian locale) |
| `mcp_server.py` | MCP server exposing 20 bank tools (vulnerable version) |
| `requirements.txt` | Pinned Python dependencies |

## Scenario mapping

| Scenario | Taxonomy | Target tool | Seed data support |
|---|---|---|---|
| 1A — Intent Breaking | Reasoning | `block_account` | Active accounts ready to be frozen |
| 1B — Memory Poisoning | Memory | `release_lien` | 3 poisoned notes + 5 active liens |
| 2A — Tool Misuse | Execution | `transfer_funds` | Funded accounts, no safeguards |
| 2B — Privilege Compromise | Identity | `write_off_loan` | 3 approved loans, no role check |
| 3A — Human Manipulation | Human-Related | `escalate_to_human` | Fraud-frozen accounts with compliance alerts |
| 3B — Agent Comm. Poisoning | Multi-Agent | `get_agent_messages` | 1 forged clearance message pre-seeded |

## Design document

See `workings/scenario-design-final.md` for the complete agreed scenario design.
