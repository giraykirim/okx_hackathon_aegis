# Official ATK capability report

Recorded: 2026-10-17T10:51:58.288628+00:00

Real FastAPI run: `5ea24c3fc1c54b9d930141a983b2a728`. Exchange writes attempted: **0**.

| Capability | Status | Evidence ID |
|---|---|---|
| ATK_PACKAGE_INSTALLED | PASS | e998a0913d2c4e7797117af0636b8379 |
| ATK_MARKET_READ | PASS | 1c91064f89504f2eb0bdf8b7e5fed510 |
| ATK_MCP_LIST_TOOLS | PASS | 6be926edf6be4205a0b278d2486cd93c |
| ATK_MCP_CALL_TOOL | PASS | 91a43152bb384db78a4c1b71afa1c260 |
| ATK_TR_ROUTING | PASS | 1c91064f89504f2eb0bdf8b7e5fed510 |
| ATK_DEMO_ACCOUNT_READ | NOT_TESTED | e998a0913d2c4e7797117af0636b8379 |
| ATK_DEMO_ORDER_SUBMISSION | NOT_TESTED | e998a0913d2c4e7797117af0636b8379 |
| ATK_ORDER_RECONCILIATION | NOT_TESTED | e998a0913d2c4e7797117af0636b8379 |

IDs resolve to persisted tool_call events in `backend/evidence/atk-official.json`.
TR routing means configured --site tr, no base-URL override, official tr.okx.com mapping and a successful public response. It does not establish private TR demo eligibility.
Private NOT_TESTED IDs point to the recorded local preflight; no authenticated operation was attempted.
Terminal commands/help, npm metadata, public ticker and hashes: `backend/evidence/atk-terminal.txt`.

Decision: NO_TRADE / NOT_SENT; missing account/model availability remains explicit.
