"""Offline development checks. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ("backend", "ml", "frontend", "web3", "tooling")


def development_env():
    env = dict(os.environ)
    paths = [env.get("PATH", "")]
    if os.name == "nt":
        import winreg

        for hive, key in (
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
            ),
        ):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    paths.append(
                        os.path.expandvars(winreg.QueryValueEx(handle, "Path")[0])
                    )
            except OSError:
                pass
    env["PATH"] = os.pathsep.join(paths)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def child_env(env):
    """Tests must not inherit operator/provider credentials."""
    return {
        key: value
        for key, value in env.items()
        if not key.startswith(("OKX_", "EVREN_", "AEGIS_"))
        and key not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"}
    }


def python_in(directory):
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def discover(root=ROOT, env=None):
    env = development_env() if env is None else env
    backend = python_in(root / "backend/.venv")
    ml_override = env.get("AEGIS_ML_PYTHON")
    ml_candidates = (
        [Path(ml_override).expanduser()]
        if ml_override
        else [python_in(root / ".venv-ml"), python_in(root.parent / "aegis/.venv")]
    )
    ml = next((path for path in ml_candidates if path.is_file()), None)
    return {
        "backend_python": str(backend) if backend.is_file() else None,
        "ml_python": str(ml) if ml else None,
        "node": shutil.which("node", path=env.get("PATH")),
        "npm": shutil.which(
            "npm.cmd" if os.name == "nt" else "npm", path=env.get("PATH")
        ),
        "git": shutil.which("git", path=env.get("PATH")),
        "rg": shutil.which("rg", path=env.get("PATH")),
    }


def suite_command(suite, tools, root=ROOT, targets=()):
    if suite == "backend":
        exe = tools.get("backend_python")
        args, cwd = ["-m", "pytest", "-q", *targets], root / "backend"
    elif suite == "ml":
        exe = tools.get("ml_python")
        if len(targets) > 1:
            raise ValueError(
                "ML accepts one --target file pattern, e.g. test_dataset.py"
            )
        args = [
            "-m",
            "unittest",
            "discover",
            "-s",
            "scripts/ml",
            "-p",
            targets[0] if targets else "test_*.py",
            "-q",
        ]
        cwd = root
    elif suite == "tooling":
        exe = sys.executable
        args, cwd = (
            [
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/devtools",
                "-p",
                "test_*.py",
                "-q",
            ],
            root,
        )
        if targets:
            raise ValueError("Tooling does not accept --target")
    else:
        exe = tools.get("node")
        cwd = root / suite
        vitest = cwd / "node_modules/vitest/vitest.mjs"
        if not vitest.is_file():
            raise ValueError(
                f"{suite}: local Vitest is missing; install locked dependencies separately"
            )
        args = [str(vitest), "run", *targets]
    if not exe:
        raise ValueError(f"{suite}: required runtime is missing; run doctor")
    return [exe, *args], cwd


def run_logged(command, cwd, log_path, env, timeout):
    started = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            log.write(b"\nDEV_RUNNER: timed out\n")
        except OSError as error:
            code = 127
            log.write(f"\nDEV_RUNNER: {error}\n".encode())
    return {
        "exit_code": code,
        "seconds": round(time.monotonic() - started, 3),
        "log": str(log_path),
    }


def new_report_dir(root=ROOT):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    folder = root / ".devtools/runs" / f"{stamp}-{os.getpid()}"
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def save_report(folder, report):
    path = folder / "summary.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Report: {path}")


def doctor(root=ROOT, env=None):
    env = development_env() if env is None else env
    tools = discover(root, env)
    checks = []
    for name, value in tools.items():
        checks.append({"name": name, "ok": bool(value), "path": value})
    modules = {
        "backend_python": ("pytest", "pytest_asyncio", "fastapi", "ruff"),
        "ml_python": ("numpy",),
    }
    for runtime, names in modules.items():
        if not tools.get(runtime):
            continue
        code = (
            "import importlib.util,json; print(json.dumps({n:importlib.util.find_spec(n) is not None for n in "
            + repr(names)
            + "}))"
        )
        try:
            probe = subprocess.run(
                [tools[runtime], "-c", code],
                capture_output=True,
                text=True,
                env=child_env(env),
                timeout=15,
                check=False,
            )
            available = json.loads(probe.stdout) if probe.returncode == 0 else {}
        except (OSError, subprocess.TimeoutExpired, ValueError):
            available = {}
        for name in names:
            checks.append(
                {"name": f"{runtime}:{name}", "ok": bool(available.get(name))}
            )
    for suite in ("frontend", "web3"):
        checks.append(
            {
                "name": f"{suite}:vitest",
                "ok": (root / suite / "node_modules/vitest/vitest.mjs").is_file(),
            }
        )
    for name in ("node", "git", "rg"):
        if tools.get(name):
            try:
                probe = subprocess.run(
                    [tools[name], "--version"],
                    capture_output=True,
                    text=True,
                    env=child_env(env),
                    timeout=10,
                    check=False,
                )
                checks.append(
                    {
                        "name": f"{name}:executable",
                        "ok": probe.returncode == 0,
                        "version": probe.stdout.splitlines()[0] if probe.stdout else "",
                    }
                )
            except (OSError, subprocess.TimeoutExpired):
                checks.append({"name": f"{name}:executable", "ok": False})
    return {
        "kind": "doctor",
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "notes": [
            "ML uses AEGIS_ML_PYTHON, .venv-ml, or the existing sibling aegis/.venv, in that order.",
            "No service, credentials, model weights or network access are required.",
        ],
    }


def integrity(root=ROOT, env=None):
    """Compare pinned files to Git checkout filters; never rewrite artifacts."""
    env = development_env() if env is None else env
    git = discover(root, env).get("git")
    if not git:
        raise ValueError("Git is missing")
    checked, issues = 0, []
    for number, line in enumerate(
        (root / ".gitattributes").read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        rel = parts[0].lstrip("/")
        if not any(part.startswith("eol=") for part in parts) or any(
            char in rel for char in "*?["
        ):
            continue
        path = (root / rel).resolve()
        if not path.is_relative_to(root.resolve()):
            issues.append({"path": rel, "issue": "path escapes project"})
            continue
        checked += 1
        if not path.is_file():
            issues.append({"path": rel, "issue": "missing file"})
            continue
        result = subprocess.run(
            [
                git,
                "--no-optional-locks",
                "-C",
                str(root),
                "cat-file",
                "--filters",
                "HEAD:" + rel,
            ],
            capture_output=True,
            env=child_env(env),
            timeout=15,
            check=False,
        )
        if result.returncode:
            issues.append({"path": rel, "issue": "Git checkout filter failed"})
        elif path.read_bytes() != result.stdout:
            raw = path.read_bytes()
            issues.append(
                {
                    "path": rel,
                    "line": number,
                    "issue": "working bytes differ from HEAD checkout",
                    "working_sha256": hashlib.sha256(raw).hexdigest(),
                    "checkout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                }
            )
    return {
        "kind": "integrity",
        "ok": not issues,
        "checked": checked,
        "issues": issues,
        "scope": "Explicit EOL-pinned paths versus HEAD checkout filters; not every historical manifest hash.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser(
        "doctor", help="Check runtimes and dependencies without changing them"
    )
    sub.add_parser("integrity", help="Read-only audit of EOL-pinned working files")
    test = sub.add_parser(
        "test", help="Run offline tests with reliable exit codes and full logs"
    )
    test.add_argument("--suite", choices=(*SUITES, "all"), default="all")
    test.add_argument("--target", action="append", default=[])
    test.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args(argv)
    env = development_env()
    folder = new_report_dir()
    try:
        if args.action in ("doctor", "integrity"):
            report = doctor(env=env) if args.action == "doctor" else integrity(env=env)
            if args.action == "doctor":
                for check in report["checks"]:
                    print(
                        f"{'OK' if check['ok'] else 'MISSING'} {check['name']} {check.get('path') or check.get('version') or ''}"
                    )
            else:
                print(
                    f"Checked {report['checked']} paths; issues: {len(report['issues'])}"
                )
            save_report(folder, report)
            return 0 if report["ok"] else 1
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        if args.suite == "all" and args.target:
            raise ValueError("Use a specific --suite with --target")
        tools = discover(env=env)
        suites = SUITES if args.suite == "all" else (args.suite,)
        plan = [
            (suite, *suite_command(suite, tools, targets=args.target))
            for suite in suites
        ]
        results = []
        for suite, command, cwd in plan:
            print(f"Running {suite}...", flush=True)
            result = run_logged(
                command, cwd, folder / f"{suite}.log", child_env(env), args.timeout
            )
            result.update({"suite": suite, "command": command, "cwd": str(cwd)})
            results.append(result)
            print(
                f"{'PASS' if result['exit_code'] == 0 else 'FAIL'} {suite}: exit={result['exit_code']} ({result['seconds']}s)"
            )
            if result["exit_code"]:
                print(f"Full failure output: {result['log']}")
        report = {
            "kind": "test",
            "ok": all(r["exit_code"] == 0 for r in results),
            "results": results,
        }
        save_report(folder, report)
        return next((r["exit_code"] for r in results if r["exit_code"]), 0)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        save_report(folder, {"kind": args.action, "ok": False, "error": str(error)})
        print(f"ERROR: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
