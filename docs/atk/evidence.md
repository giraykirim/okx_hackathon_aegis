# Official ATK evidence

The running backend invokes pinned `@okx_ai/okx-trade-cli@1.4.8` as a Node subprocess. It does not substitute Python OKX REST. Both the autonomous loop and external assessment service produce `ATK_RECEIPT` events in the existing v2 Event.details field; no Event schema changed.

Each actual public ticker/instrument invocation records: exact argv, toolkit version, regional site, backend run ID, requested/completed UTC timestamps, venue market timestamp when present, elapsed wall-clock milliseconds, source mode, PASS/FAIL, raw stdout SHA-256, parsed-result SHA-256, and error type on failure. Instrument metadata has no exchange timestamp, so its `market_timestamp` is null; the ticker supplies the venue timestamp. PASS means the CLI returned the expected JSON envelope, while full observation validation and freshness remain separate checks.

`result_sha256` is SHA-256 of Python JSON with sorted keys and compact separators; `stdout_sha256` hashes the exact returned bytes. Public market prices and metadata are not secrets. Provider stderr, inherited credentials, private environment values and user OKX configuration are excluded. The child runs with forced demo transport and the configured site (`tr` for TR accounts); this does not prove private demo availability.

Reproduce against the running loopback backend:

```sh
cd backend
uv run python -m scripts.http_smoke
uv run python -m scripts.prove_service
```

Inspect `backend/evidence/http-smoke.json` for autonomous calls and `backend/evidence/amendment-http.json` for actual assessment calls. These scripts call HTTP; the backend spawns ATK. No coding-assistant-only MCP registration is counted. `backend/evidence/latest.json` remains separate direct-runtime proof, with explicitly labeled MOCK scenarios.

No real demo order was attempted during this amendment. EVREN authenticated discovery/generation and LAN LAYA inference remain separate capabilities; neither a public schema nor a fallback is integration proof.
