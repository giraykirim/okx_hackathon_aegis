# Official OKX Agent Trade Kit evidence

FastAPI uses packages published by [OKX’s official Agent Trade Kit project](https://github.com/okx/agent-trade-kit). Both global executables and backend dependencies are installed at 1.4.8; their entrypoint SHA-256 values match. Installation was already present, so no global reinstall was needed. Captured npm registry tarball/integrity metadata, macOS M2 arm64, Node/npm/Python versions and installed `--help` are in `backend/evidence/atk-terminal.txt`.

Autonomous market observation defaults to a **real MCP stdio client** using the official MCP SDK. It launches the pinned official server as a separate process with `--modules market --read-only --site tr --demo`, performs `tools/list`, checks discovered schemas/read-only annotations and calls `market_get_ticker` / `market_get_instruments`. Public arguments explicitly use `demo=false`; the response confirms `readOnly=true`, `hasAuth=false`. These calls originate in FastAPI’s autonomous cycle. A coding-assistant-only MCP registration is not counted as proof.

The installed CLI supports the exact requested public command:

```sh
OKX_SITE=tr okx market ticker BTC-USDT --json
```

The proof runs that argv with an allowlisted environment and isolated profile/OAuth/log directory. Backend children never inherit personal exchange credentials, `OKX_API_BASE_URL`, `NODE_OPTIONS` or proxy overrides. A controlled Node preload isolates `os.homedir()` without changing the user’s HOME. Both transports invoke official ATK; neither uses a substitute exchange REST connector.

`AEGIS_ATK_TRANSPORT=cli` explicitly selects the existing argv-list subprocess transport; there is no automatic retry on an ambiguous failure. Both legacy quantity and notional assessment services retain official CLI reads, preserving their frozen CLI-only receipt identity. MCP observations have their own toolkit identity. Existing `ATK_RECEIPT` events and schemas remain supported.

Every invocation creates a sanitized `tool_call` record inside existing Event.details:

```text
run_id, tool_id, request_ts, source_ts, source_mode, symbol, latency_ms,
success, response_hash, status_code, evidence_id
```

The event ID equals `evidence_id`. Request timestamps and monotonic durations are measured at the invocation. Ticker `source_ts` comes from the venue’s `ts`; instrument metadata/discovery have UNKNOWN source time. Neither transport exposes the upstream HTTP status, so `status_code=UNKNOWN`. Missing responses use UNKNOWN hashes; latency uses UNKNOWN only when timing is unavailable. Hashes use parsed JSON, sorted keys, compact separators, UTF-8 and finite numbers only. Provider stderr, private payloads and exception text are excluded; private response hashes remain opaque. Autonomous attempts persist immediately, including cancellation and private calls. Assessment evidence is linked to the assessment/request ID.

Current real proof: `backend/evidence/atk-official.json`, [eight-capability report](CAPABILITIES.md), and the redacted terminal transcript. It captures FastAPI start → official MCP discovery/calls → real observation → autonomous NO_TRADE → VERIFY → AUDIT → stop, plus SSE replay. Models/account facts remain unavailable; execution is NOT_SENT.

Reproduce with the loopback MARKET_ONLY server stopped at the agent level:

```sh
cd backend
npm ci
uv sync --python 3.12 --frozen
# Terminal 1
uv run uvicorn aegis.app:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
# Terminal 2
uv run python -m scripts.prove_atk
uv run python -m scripts.http_smoke
uv run python -m scripts.prove_service
node --test tests/atk-mcp-tools.test.mjs
uv run pytest -q
uv run python -m scripts.export_contract --check
```

The local personal profile has TR/demo flags set, existing credential fields preserved and file mode 0600. Values are never printed or copied into backend/public proof. Presence does not establish validity, permission scope, a separately created API passphrase or regional demo support. Those capabilities remain NOT_TESTED. To complete them privately, use the installed guided `okx config init`, select TR/demo and enter a DEMO API key, secret and the independently created API passphrase; grant Read+Trade only, no Withdraw. Confirm TR demo availability before enabling the separate backend `.env` demo interlocks. The backend deliberately ignores personal profiles and requires isolated demo credentials. No private account query or exchange order was attempted in this proof.
