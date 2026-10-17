"""Bounded LAN inference server for the V2 Tuned (`seed-17`) LAYA checkpoint on port 8771.

Runs alongside the existing port 8770 (`base`) server without touching `models/aegis_laya_selected`.
Exposes the exact same `/healthz` and `/classify` contract as `serve_selected.py`.
"""

import argparse
import hashlib
import json
import os
import site
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_SITE = ROOT.parent / "aegis/.venv/Lib/site-packages"
if VENV_SITE.is_dir():
    site.addsitedir(str(VENV_SITE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from reviewed_learning import BOOLS
from serve_selected import InferenceServer, Runtime, verified_selection

TUNED_RUN_ID = "option1-881rows-20261017T224137698785Z"
TUNED_CKPT = ROOT / "models/reviewed_development" / TUNED_RUN_ID / "seed-17"
TUNED_META = ROOT / "ml/reviewed_development" / TUNED_RUN_ID / "seed-17.json"


def ensure_selection_file(directory=TUNED_CKPT, meta_path=TUNED_META):
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    hashes = meta["checkpoint_hashes"]
    version = hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()
    selection_obj = {
        "selected": "v2-tuned-seed17",
        "version": version,
        "hashes": hashes,
        "source_run": TUNED_RUN_ID,
    }
    sel_file = directory / "selection.json"
    if not sel_file.exists():
        sel_file.write_text(
            json.dumps(selection_obj, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return verified_selection(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("0.0.0.0", "127.0.0.1"), default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8771)
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
    selection, version = ensure_selection_file()
    import laya
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("Existing local CUDA runtime required")
    agent = laya.load(str(TUNED_CKPT), device="cuda", compile=False, fast=False)
    runtime = Runtime(agent, version, torch.cuda.synchronize)

    warmup_payload = {
        "state": {
            "operational": {
                "symbol": "BTC-USDT",
                "site": "tr",
                "source_mode": "MARKET_ONLY",
                "feed_age_seconds": 2,
                "intent_requested": False,
                "quantity": "0.00010000",
                "account_known": True,
                "approval_available": True,
                **{
                    key: False
                    for key in BOOLS
                    if key not in ("account_known", "approval_available")
                },
            }
        },
        "run_id": "service-warmup-v2-tuned",
        "correlation_id": "service-warmup-v2-tuned",
    }
    warmup = runtime.classify(warmup_payload)
    if warmup["abstained"] or runtime.inference_calls != 1:
        raise RuntimeError("Real V2-tuned checkpoint warmup failed; service not started")

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
                    "warmup": warmup,
                }
            ),
            flush=True,
        )
        server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
