# Step 1: Entra authorization

This variant keeps the vulnerable baseline unchanged and moves bank tools to an
authenticated Streamable HTTP MCP boundary. The `write_off_loan` tool requires
the `CreditCommittee` application role from a validated delegated access token.

## Configuration

Add these values to the repository-root `.env` file:

```text
ENTRA_TENANT_ID=<directory tenant ID>
ENTRA_MCP_API_CLIENT_ID=<midtownbank-mcp-api-dev application client ID>
ENTRA_MCP_SCOPE=api://<API client ID>/access_as_user
ENTRA_AGENT_CLIENT_ID=<midtownbank-agent-client-dev application client ID>
ENTRA_AGENT_CLIENT_SECRET=<client secret value>
ENTRA_REDIRECT_URI=http://localhost:8501
MCP_SERVER_URL=http://localhost:8000/mcp
```

The API registration must expose `access_as_user`. Assign either the `Teller`
or `CreditCommittee` app role to each test employee for the API enterprise
application. Do not put role names in prompts or tool arguments.

## Run locally

From the repository root, start the protected MCP server:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m agents.hardened.steps.step_01_authorization.server
```

In a second terminal, start the employee UI:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\streamlit.exe run src\agents\hardened\steps\step_01_authorization\app.py
```

Open `http://localhost:8501`, sign in, and run Scenario 2B with a Teller user.
The expected result is `403 FORBIDDEN: INSUFFICIENT_PRIVILEGES`, with no
loan-state change. The response intentionally does not disclose the required
role.

Authorization decisions are appended to
`data/attack-logs/hardened-step-01-authorization.jsonl`. Override the location
with `AUTHORIZATION_AUDIT_LOG` when isolating experiment runs.

## Focused validation

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest agents.hardened.steps.step_01_authorization.test_auth -v
```