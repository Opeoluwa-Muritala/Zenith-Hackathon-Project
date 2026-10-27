"""Export FastAPI's in-memory OpenAPI document without network or database access."""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "api" / "openapi.json"


def export_openapi() -> dict:
    document = app.openapi()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUTPUT.with_suffix(".yaml").write_text(
        yaml.safe_dump(document, sort_keys=True), encoding="utf-8"
    )
    return document


if __name__ == "__main__":
    export_openapi()
