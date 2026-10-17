# Official ATK verification plan

Continue the existing backend and frozen API. Baseline: official CLI/MCP 1.4.8 already installed; Apple M2 arm64; Node 24.13.1, npm 11.8.0, system Python 3.13.0 and project Python 3.12.13. Live isolated MCP discovery and public ticker probe succeeded. Private demo capability is unverified.

1. Capture installed help, registry provenance and an isolated CLI public ticker.
2. Test and implement a bounded Node MCP SDK client which discovers and validates the actual public tool schemas before calling. Default autonomous observations to MCP; retain CLI transport and legacy service CLI receipts unchanged.
3. Add sanitized tool-call evidence inside existing Event.details, with actual timestamps, duration, hashes and UNKNOWN for unavailable source/HTTP status. Capabilities reference those evidence IDs; no private payloads or inherited credentials.
4. Preserve the local profile credentials, set TR/demo flags only, and leave private account/order capabilities NOT_TESTED until independently verified. Never submit a live order.
5. Execute offline regression tests, frozen contract checks, real HTTP autonomous observation/NO_TRADE, SSE replay and actual CLI/MCP proof. Review the patch and capture a jury capability matrix with evidence IDs.

No frontend, web3, model or frozen DTO edits. CLI receipts keep their existing toolkit identity; MCP evidence uses its own exact identity.
