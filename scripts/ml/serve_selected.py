"""Bounded LAN SHADOW inference for the hash-verified selected LAYA checkpoint.

No execution authority, source mapping approval, credentials, training or telemetry.
Complete typed operational states are caller assertions, not verified backend facts.
Legacy incomplete Observation inputs abstain; never invent missing context.
"""

import argparse
import hashlib
import json
import math
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from candidate_preflight import strict_json
from reviewed_learning import ROOT, state_from_context

from ml.label_policy import LABELS, QUESTIONS

MAX_BODY = 16 * 1024
CHECKPOINT = ROOT / "models/aegis_laya_selected"
RESPONSE_FIELDS = {"label", "confidence", "abstained", "model_version", "latency_ms"}


def verified_selection(directory=CHECKPOINT):
    record = strict_json((directory / "selection.json").read_text(encoding="utf-8"))
    for name, expected in record["hashes"].items():
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("checkpoint path escaped selected directory")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                raise ValueError("selected checkpoint integrity failure")
    version = hashlib.sha256(
        json.dumps(record["hashes"], sort_keys=True).encode()
    ).hexdigest()
    if record["version"] != version or record["hashes"].get("questions.json") is None:
        raise ValueError("selected version/question binding mismatch")
    questions = strict_json((directory / "questions.json").read_text(encoding="utf-8"))
    if questions != QUESTIONS:
        raise ValueError("selected question contract changed")
    return record, f"aegis-laya-{record['selected']}-{version[:12]}"


def normalized_request(payload):
    if not isinstance(payload, dict) or set(payload) != {
        "state",
        "run_id",
        "correlation_id",
    }:
        raise ValueError("unsupported envelope")
    for field in ("run_id", "correlation_id"):
        if not isinstance(payload[field], str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,128}", payload[field]
        ):
            raise ValueError("unsupported correlation metadata")
    state = payload["state"]
    if isinstance(state, str):
        if len(state) > MAX_BODY:
            raise ValueError("state too long")
        state = strict_json(state)
    if (
        not isinstance(state, dict)
        or set(state) != {"operational"}
        or not isinstance(state["operational"], dict)
    ):
        raise ValueError("incomplete legacy or unsupported state")
    normalized, unknown = state_from_context(state["operational"])
    if unknown:
        raise ValueError("required context unknown")
    if len(normalized) > MAX_BODY:
        raise ValueError("normalized state too long")
    return normalized


class Runtime:
    def __init__(self, agent, model_version, synchronize=lambda: None):
        self.agent = agent
        self.model_version = model_version
        self.synchronize = synchronize
        self.lock = threading.Lock()
        self.inference_calls = 0
        self.fallback_calls = 0

    def fallback(self, start=None):
        self.fallback_calls += 1
        return {
            "label": "REVIEW",
            "confidence": 0.0,
            "abstained": True,
            "model_version": self.model_version,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3)
            if start is not None
            else 0.0,
        }

    def classify(self, payload):
        start = time.perf_counter()
        try:
            state = normalized_request(payload)
        except (ValueError, TypeError, KeyError, OverflowError):
            return self.fallback(start)
        if not self.lock.acquire(blocking=False):
            return self.fallback(start)
        try:
            # This is the actual checkpoint predict path, not classify()/oracle rules.
            result = self.agent.predict(state, QUESTIONS)
            self.synchronize()
            self.inference_calls += 1
            answer = result["answers"]["operational_state"]
            usage = result["usage"]
            label, confidence = answer["choice"], answer["confidence"]
            if (
                label not in LABELS
                or type(confidence) not in (float, int)
                or not math.isfinite(confidence)
                or not 0 <= confidence <= 1
                or usage.get("truncated")
                or usage.get("state_tokens_dropped")
                or usage.get("truncated_questions")
                or answer.get("abstained")
            ):
                return self.fallback(start)
            return {
                "label": label,
                "confidence": float(confidence),
                "abstained": False,
                "model_version": self.model_version,
                "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            }
        except Exception:  # noqa: BLE001 - fail-closed HTTP boundary, never leak model errors
            # Never return stack traces, inputs, identifiers, file paths or model errors.
            return self.fallback(start)
        finally:
            self.lock.release()


class InferenceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 8

    def __init__(self, address, runtime):
        self.runtime = runtime
        self.capacity = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.capacity.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.capacity.release()

    def handle_error(self, request, client_address):
        pass  # No client addresses or request text in logs.


class Handler(BaseHTTPRequestHandler):
    server_version = "AEGISShadow/1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format, *args):
        pass  # Never log bodies, headers, correlation IDs or client addresses.

    def reply(self, status, data):
        body = json.dumps(data, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self.reply(
                200,
                {
                    "status": "ready",
                    "model_version": self.server.runtime.model_version,
                    "inference_calls": self.server.runtime.inference_calls,
                    "fallback_calls": self.server.runtime.fallback_calls,
                    "shadow_only": True,
                    "execution_authority": False,
                },
            )
        else:
            self.reply(404, self.server.runtime.fallback())

    def do_POST(self):
        if self.path != "/classify":
            self.reply(404, self.server.runtime.fallback())
            return
        start = time.perf_counter()
        lengths = self.headers.get_all("Content-Length", [])
        if (
            len(lengths) != 1
            or not lengths[0].isdigit()
            or self.headers.get("Transfer-Encoding") is not None
            or self.headers.get("Content-Encoding", "identity") != "identity"
            or self.headers.get_content_type() != "application/json"
        ):
            self.reply(200, self.server.runtime.fallback(start))
            return
        size = int(lengths[0])
        if size < 1 or size > MAX_BODY:
            self.reply(413, self.server.runtime.fallback(start))
            return
        try:
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("incomplete body")
            payload = strict_json(raw.decode("utf-8"))
        except (ValueError, OSError, UnicodeError, RecursionError):
            self.reply(200, self.server.runtime.fallback(start))
            return
        self.reply(200, self.server.runtime.classify(payload))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("0.0.0.0", "127.0.0.1"), default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--runtime-file", type=Path, required=True)
    args = parser.parse_args()
    runtime_path = args.runtime_file.resolve()
    if (
        not runtime_path.is_relative_to(ROOT / "ml/lan_inference")
        or runtime_path.exists()
        or not 1024 <= args.port <= 65535
    ):
        parser.error("new owned runtime file and nonprivileged port required")
    os.environ.update(
        HF_HOME=str(ROOT / "models/hf-cache"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    )
    selection, version = verified_selection()
    import laya
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Existing local CUDA runtime required; no automatic install")
    agent = laya.load(str(CHECKPOINT), device="cuda", compile=False, fast=False)
    runtime = Runtime(agent, version, torch.cuda.synchronize)
    # Verify actual GPU inference before claiming readiness. No dataset/final-test read.
    from reviewed_learning import BOOLS

    warmup_payload = {
        "state": {
            "operational": {
                "symbol": "BTC-USDT",
                "site": "tr",
                "source_mode": "MARKET_ONLY",
                "feed_age_seconds": 2,
                "intent_requested": False,
                "quantity": "0.0001",
                **{key: False for key in BOOLS},
            }
        },
        "run_id": "service-warmup",
        "correlation_id": "service-warmup",
    }
    warmup = runtime.classify(warmup_payload)
    if warmup["abstained"] or runtime.inference_calls != 1:
        raise RuntimeError(
            "Real selected-checkpoint warmup failed; service not started"
        )
    with InferenceServer((args.host, args.port), runtime) as server:
        record = {
            "pid": os.getpid(),
            "host": args.host,
            "port": args.port,
            "model_version": version,
            "checkpoint_version": selection["version"],
            "selected": selection["selected"],
            "checkpoint_hashes": selection["hashes"],
            "gpu": torch.cuda.get_device_name(0),
            "laya": laya.__version__,
            "torch": torch.__version__,
            "warmup_real_inference": warmup,
            "shadow_only": True,
            "execution_authority": False,
            "production_approved": False,
            "legacy_context_mapping_approved": False,
            "auth": "NONE_ISOLATED_HACKATHON_LAN_ONLY",
        }
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        with runtime_path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(
            json.dumps(
                {
                    "ready": True,
                    "pid": os.getpid(),
                    "host": args.host,
                    "port": args.port,
                    "model_version": version,
                }
            ),
            flush=True,
        )
        server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
