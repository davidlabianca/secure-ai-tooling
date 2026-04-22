#!/usr/bin/env python3
"""
Pre-commit framework hook that re-validates every yaml against its schema
when the master schema `risk-map/schemas/riskmap.schema.json` changes.

A change to the master schema can affect any downstream yaml's validity via
`$ref` resolution, so we run check-jsonschema for every yaml/schema pair in
one pass. Source files are discovered by pairing each `*.schema.json` under
`risk-map/schemas/` with a same-named `*.yaml` under `risk-map/yaml/` —
this avoids a hardcoded list that would drift if a file is added or renamed.

Invoked by the pre-commit framework with no filenames (`pass_filenames:
false`). Only scheduled when `risk-map/schemas/riskmap.schema.json` itself
is staged — see `.pre-commit-config.yaml`.
"""

import os
import subprocess
import sys
from pathlib import Path

_SCHEMA_DIR = Path("risk-map/schemas")
_YAML_DIR = Path("risk-map/yaml")
_MASTER_SCHEMA_NAME = "riskmap.schema.json"


def _find_pairs() -> list[tuple[Path, Path]]:
    """Discover (schema, yaml) pairs for every schema with a matching yaml.

    The master schema (riskmap.schema.json) is excluded — it is the trigger,
    not a target. Schemas without a matching yaml are skipped silently.
    """
    pairs: list[tuple[Path, Path]] = []
    for schema in sorted(_SCHEMA_DIR.glob("*.schema.json")):
        if schema.name == _MASTER_SCHEMA_NAME:
            continue
        stem = schema.name.removesuffix(".schema.json")
        yaml_file = _YAML_DIR / f"{stem}.yaml"
        if yaml_file.is_file():
            pairs.append((schema, yaml_file))
    return pairs


def main(argv: list[str]) -> int:
    """Run check-jsonschema for every yaml/schema pair.

    Returns 0 if every pair validates cleanly, the first non-zero returncode
    otherwise. All pairs are attempted regardless of earlier failures so the
    user sees every error in one pass.
    """
    del argv  # framework passes no filenames; discovery is filesystem-based

    pairs = _find_pairs()
    if not pairs:
        return 0

    base_uri = f"file://{os.getcwd()}/risk-map/schemas/"
    exit_code = 0
    for schema, yaml_file in pairs:
        cmd = [
            "check-jsonschema",
            "--base-uri",
            base_uri,
            "--schemafile",
            str(schema),
            str(yaml_file),
        ]
        result = subprocess.run(cmd)
        if result.returncode != 0 and exit_code == 0:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
