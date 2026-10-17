"""Real official CLI + FastAPI -> MCP stdio proof. Public reads only; no credential output."""

import asyncio
import hashlib
import json
import shutil
import sys
import tempfile
import time
import tomllib
from pathlib import Path

import httpx

from aegis.atk import ATK
from aegis.models import new_id, utcnow
from aegis.settings import ROOT, Settings

CAPABILITIES = (
    "ATK_PACKAGE_INSTALLED",
    "ATK_MARKET_READ",
    "ATK_MCP_LIST_TOOLS",
    "ATK_MCP_CALL_TOOL",
    "ATK_TR_ROUTING",
    "ATK_DEMO_ACCOUNT_READ",
    "ATK_DEMO_ORDER_SUBMISSION",
    "ATK_ORDER_RECONCILIATION",
)


def profile_flags():
    path = Path.home() / ".okx/config.toml"
    if not path.exists():
        return {"exists": False, "private_capabilities": "NOT_TESTED"}
    config = tomllib.loads(path.read_text())
    profile = config.get("profiles", {}).get(config.get("default_profile", "default"), {})
    return {
        "exists": True,
        "site": profile.get("site"),
        "demo": profile.get("demo"),
        "credentials_present": {
            key: bool(profile.get(key)) for key in ("api_key", "secret_key", "passphrase")
        },
        "file_mode": oct(path.stat().st_mode & 0o777),
        "credential_validity": "NOT_TESTED",
        "permissions": "NOT_TESTED",
        "regional_demo_support": "NOT_TESTED",
        "backend_uses_personal_profile": False,
    }


async def capture(argv, env, transcript):
    requested, started = utcnow(), time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *argv, cwd=ROOT, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(), 25)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.communicate()
        raise
    output = stdout.decode()
    transcript.extend(["$ " + " ".join(argv), output.rstrip(), f"exit_code={process.returncode}", ""])
    assert process.returncode == 0, "Read-only verification command failed (stderr withheld)"
    return {
        "evidence_id": new_id(),
        "argv": argv,
        "request_ts": requested.isoformat(),
        "latency_ms": (time.perf_counter() - started) * 1000,
        "exit_code": process.returncode,
        "stdout": output,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
    }


async def main():
    settings = Settings()
    assert settings.okx_site == "tr" and settings.source_mode == "MARKET_ONLY"
    assert settings.control_token and settings.atk_transport == "mcp"
    proof = {
        "recorded_at": utcnow().isoformat(),
        "official_source": "https://github.com/okx/agent-trade-kit",
        "source_mode": "MARKET_ONLY",
        "exchange_writes_attempted": 0,
        "profile": profile_flags(),
        "commands": [],
        "public_deployment": "NOT_TESTED",
    }
    transcript = [
        "AEGIS official ATK terminal proof (public data only)",
        "Commands run with an allowlisted environment and isolated OKX profiles/OAuth/log directory.",
        "MCP server is a separate child process: --modules market --read-only --site tr --demo.",
        "Public MCP tool arguments explicitly set demo=false. No account keys reach either child.",
        "",
    ]
    atk = ATK(settings)
    with tempfile.TemporaryDirectory(prefix="aegis-official-proof-") as directory:
        env = atk.child_environment(Path(directory), private=False)
        env["NODE_OPTIONS"] = "--import=" + str(ROOT / "aegis/atk-isolation.mjs")
        for argv in (
            ["node", "-v"],
            ["npm", "-v"],
            ["python3", "--version"],
            [sys.executable, "--version"],
            ["uname", "-sm"],
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            ["sw_vers"],
            ["npm", "list", "-g", "--depth=0", "--json"],
            ["okx", "--version"],
            ["okx", "--help"],
            ["okx", "market", "ticker", "--help"],
            ["okx-trade-mcp", "--version"],
            ["okx-trade-mcp", "--help"],
            ["okx", "config", "init", "--help"],
        ):
            proof["commands"].append(await capture(argv, env, transcript))
        assert int(proof["commands"][0]["stdout"].lstrip("v").split(".")[0]) >= 18
        help_text = next(c["stdout"] for c in proof["commands"] if c["argv"] == ["okx", "--help"])
        assert "--json" in help_text
        cli = await capture(["okx", "market", "ticker", "BTC-USDT", "--json"], env, transcript)
        rows = json.loads(cli["stdout"])
        assert rows[0]["instId"] == "BTC-USDT" and rows[0]["ts"]
        cli["environment"] = {"OKX_SITE": "tr", "credential_variables": "ABSENT", "profile": "ISOLATED"}
        proof["cli_public_market"] = cli
        for package in ("okx-trade-cli", "okx-trade-mcp"):
            proof["commands"].append(
                await capture(
                    [
                        "npm",
                        "view",
                        "@okx_ai/" + package + "@1.4.8",
                        "version",
                        "dist.integrity",
                        "dist.tarball",
                        "--json",
                    ],
                    env,
                    transcript,
                )
            )
        proof["installed_binaries"] = {}
        for package in ("okx-trade-cli", "okx-trade-mcp"):
            local = ROOT / f"node_modules/@okx_ai/{package}/dist/index.js"
            # Resolve globals directly through their executable symlinks.
            installed = Path(shutil.which("okx" if package == "okx-trade-cli" else "okx-trade-mcp")).resolve()
            hashes = {
                name: hashlib.sha256(p.read_bytes()).hexdigest()
                for name, p in (("global", installed), ("backend", local))
            }
            assert hashes["global"] == hashes["backend"]
            proof["installed_binaries"][package] = hashes
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
        health = (await client.get("/api/health")).json()
        assert health["source_mode"] == "MARKET_ONLY" and not health["running"]
        headers = {"Authorization": "Bearer " + settings.control_token.get_secret_value()}
        start = await client.post("/api/agent/start", headers=headers)
        start.raise_for_status()
        run_id = start.json()["run_id"]
        try:
            for _ in range(200):
                decisions = (await client.get("/api/decisions")).json()
                decision = next((d for d in decisions if d["run_id"] == run_id), None)
                if decision:
                    break
                await asyncio.sleep(0.2)
            else:
                raise AssertionError("No autonomous decision within 40 seconds")
        finally:
            stop = await client.post("/api/agent/stop", headers=headers)
            stop.raise_for_status()
            assert stop.json()["running"] is False
        snapshot = (await client.get("/api/snapshot")).json()
        events = [e for e in (await client.get("/api/events?limit=1000")).json() if e["run_id"] == run_id]
        tools = [e for e in events if e["type"] == "tool_call"]
        assert len(tools) >= 5
        evidence_ids = {e["id"] for e in tools}
        assert {e["details"]["tool_call"]["tool_id"].split(":")[-1] for e in tools} >= {
            "tools/list",
            "market_get_ticker",
            "market_get_instruments",
        }
        assert all(e["details"]["tool_call"]["success"] for e in tools)
        assert decision["proposed_action"] == "NO_TRADE" and decision["execution_status"] == "NOT_SENT"
        assert snapshot["observation"]["account_known"] is False
        phases = [e["details"].get("phase") for e in events if e["details"].get("phase")]
        assert phases == ["OBSERVE", "CLASSIFY", "REASON", "RISK_CHECK", "NO_TRADE", "VERIFY", "AUDIT"]
        report = {key: snapshot["capabilities"][key] for key in CAPABILITIES}
        for key, capability in report.items():
            expected = "NOT_TESTED" if key in CAPABILITIES[-3:] else "PASS"
            assert capability["status"] == expected
            assert capability["evidence"] and set(capability["evidence"]) <= evidence_ids
        # Exercise real SSE transport using an evidence event ID, without a coding-agent-only MCP shortcut.
        async with client.stream("GET", "/api/stream", headers={"Last-Event-ID": tools[0]["id"]}) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    proof["sse_replayed_event_id"] = json.loads(line[6:])["id"]
                    break
        proof.update(run_id=run_id, decision=decision, snapshot=snapshot, events=events, capabilities=report)
        transcript.extend(
            [
                "$ uv run python -m scripts.prove_atk  # FastAPI start/stop; key withheld",
                f"run_id={run_id}",
                "PASS: real MCP tools/list + tools/call persisted in FastAPI timeline",
                "PASS: real market observation -> autonomous NO_TRADE -> NOT_SENT -> AUDIT; stopped",
                json.dumps(report, indent=2),
                "No account read, order submission, or reconciliation attempted.",
            ]
        )
    (ROOT / "evidence/atk-official.json").write_text(json.dumps(proof, indent=2) + "\n")
    (ROOT / "evidence/atk-terminal.txt").write_text("\n".join(transcript) + "\n")
    matrix = [
        "# Official ATK capability report",
        "",
        "Recorded: " + proof["recorded_at"],
        "",
        "Real FastAPI run: `" + run_id + "`. Exchange writes attempted: **0**.",
        "",
        "| Capability | Status | Evidence ID |",
        "|---|---|---|",
    ]
    matrix.extend(
        f"| {key} | {value['status']} | {', '.join(value['evidence'])} |" for key, value in report.items()
    )
    matrix.extend(
        [
            "",
            "IDs resolve to persisted tool_call events in `backend/evidence/atk-official.json`.",
            "TR routing means configured --site tr, no base-URL override, official tr.okx.com mapping and a successful public response. It does not establish private TR demo eligibility.",
            "Private NOT_TESTED IDs point to the recorded local preflight; no authenticated operation was attempted.",
            "Terminal commands/help, npm metadata, public ticker and hashes: `backend/evidence/atk-terminal.txt`.",
            "",
            "Decision: NO_TRADE / NOT_SENT; missing account/model availability remains explicit.",
        ]
    )
    (ROOT.parent / "docs/atk/CAPABILITIES.md").write_text("\n".join(matrix) + "\n")
    print("PASS: official global CLI ticker; actual FastAPI -> MCP discovery/calls -> NO_TRADE; SSE replay")
    print("Evidence: evidence/atk-official.json and evidence/atk-terminal.txt; private demo NOT_TESTED")


if __name__ == "__main__":
    asyncio.run(main())
