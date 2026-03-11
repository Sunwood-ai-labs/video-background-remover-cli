"""Worker script executed by the MatAnyone Python runtime.

This script exists so the host project can call into `matanyone2-runtime`
through a normal Python import instead of shelling out to the package CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from matanyone2.api import run_pipeline


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        raise SystemExit("usage: matanyone_import_worker.py <payload.json> <result.json>")

    payload_path = Path(args[0])
    result_path = Path(args[1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    result = run_pipeline(**payload)
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
