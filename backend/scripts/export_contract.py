import argparse
import hashlib
from copy import deepcopy

import yaml

from aegis.app import create_app
from aegis.settings import ROOT

FROZEN_V2_SHA256 = "a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae"
V2_PATH = ROOT.parent / "contracts/openapi.yaml"
SERVICE_PATH = ROOT.parent / "contracts/service-openapi.yaml"
SERVICE_ROUTES = {"/api/v1/risk/evaluate", "/api/v1/service"}


def check_frozen_v2(schema):
    if hashlib.sha256(V2_PATH.read_bytes()).hexdigest() != FROZEN_V2_SHA256:
        raise ValueError("Frozen v2 contract bytes changed")
    frozen = yaml.safe_load(V2_PATH.read_text(encoding="utf-8"))
    for path, expected in frozen["paths"].items():
        if schema["paths"].get(path) != expected:
            raise ValueError("Existing v2 route changed: " + path)
    for kind, definitions in frozen["components"].items():
        for name, expected in definitions.items():
            if schema["components"].get(kind, {}).get(name) != expected:
                raise ValueError("Existing v2 schema changed: " + name)


def additive_schema(schema):
    result = {
        "openapi": schema["openapi"],
        "info": {"title": "AEGIS Risk Check Service — additive contract", "version": "1.0.0"},
        "paths": {p: deepcopy(schema["paths"][p]) for p in sorted(SERVICE_ROUTES)},
        "components": {},
    }
    visited = set()

    def collect(value):
        if isinstance(value, dict):
            reference = value.get("$ref", "")
            if reference.startswith("#/components/") and reference not in visited:
                visited.add(reference)
                _, _, kind, name = reference.split("/")
                definition = deepcopy(schema["components"][kind][name])
                result["components"].setdefault(kind, {})[name] = definition
                collect(definition)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(result["paths"])
    result["components"]["securitySchemes"] = {
        "AEGISServiceKey": deepcopy(schema["components"]["securitySchemes"]["AEGISServiceKey"])
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    schema = create_app().openapi()
    check_frozen_v2(schema)
    additive = additive_schema(schema)
    if args.check:
        if not SERVICE_PATH.exists() or yaml.safe_load(SERVICE_PATH.read_text(encoding="utf-8")) != additive:
            raise SystemExit("FAIL: additive service contract differs from the application")
        print("PASS: frozen v2 unchanged; existing routes/schemas and additive service contract match")
        return
    SERVICE_PATH.write_text(
        yaml.safe_dump(additive, sort_keys=False, allow_unicode=True), encoding="utf-8", newline="\n"
    )
    print("Preserved frozen v2; exported contracts/service-openapi.yaml")


if __name__ == "__main__":
    main()
