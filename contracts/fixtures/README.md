# Explicit integration fixtures

`risk-notional-mock.request.json` is the new string-notional request. `requester_context: null` is valid. `risk-notional-mock.response.json` is an actual response captured from the local MOCK HTTP server by `backend/scripts/prove_mock_contract.py`; it is an example with its recorded timestamp/evidence IDs, not current market or on-chain evidence. Small valid requests remain UNAVAILABLE because trustworthy caller account data does not exist.

`mock-halt.request.json` is the unchanged v2 scenario request; its corresponding response is an actual captured MOCK Decision. Existing Event and Decision shapes remain unchanged.

Correlation is idempotent within the deployment credential + server-selected source mode + policy version: the same request ID and effective intent returns the original timestamp/result/evidence IDs across restarts. Decimal spellings such as `10.0` and `10.00` are equivalent. Context is excluded because it has no authority. Reusing an ID with a different intent returns 409. A cached result is historical, not a new freshness guarantee; use a new ID for reassessment. Identical replays do not consume another assessment admission or append audit events.

The response has the ten fields requested by Person 1's task. No current path emits ALLOW_FOR_FURTHER_CHECKS. This enum is reserved for a future implementation with verified prerequisites; it would still not authorize an exchange order. Chain receipt is always null today. Decimal input must be a plain decimal **string**, not a JSON number; NO_TRADE alone may use `"0"`.

Context may contain harmless client hints, nulls and nested JSON, but is never forwarded to models, used in policy, or stored. Credential/private-balance fields and excessive nesting are rejected with sanitized validation errors; do not submit secrets. The body has the existing 2 KiB limit.

Start from the repository root:

```sh
cd backend
uv run python -m scripts.init_local
uv run python -m scripts.run_mock --port 8001
```

In another terminal, from `backend/`:

```sh
curl --fail-with-body --silent --show-error \
  --config data/mock-service.curl \
  --header 'Content-Type: application/json' \
  --data-binary @../contracts/fixtures/risk-notional-mock.request.json \
  http://127.0.0.1:8001/api/v1/risk/evaluate
```

The curl config holds only the local assessment credential in an ignored mode-0600 file. Do not print/share it. Run `uv run python -m scripts.prove_mock_contract --port 8001` to exercise actual health, Start/Stop, autonomous NO_TRADE, HALT, idempotent assessment, conflict detection and SSE resume. This does not certify real market, model or on-chain availability.
