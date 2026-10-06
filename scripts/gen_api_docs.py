"""Regenerate the endpoint inventory in docs/api.md from the exported schema."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "backend" / "openapi.json"
DOC = ROOT / "docs" / "api.md"
START = "<!-- GENERATED ENDPOINTS START -->"
END = "<!-- GENERATED ENDPOINTS END -->"


def main() -> None:
    """Replace the generated endpoint table without touching hand-written prose."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    rows = ["| Method | Path | Summary | Tag |", "|---|---|---|---|"]
    for path, methods in sorted(schema.get("paths", {}).items()):
        for method, operation in sorted(methods.items()):
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = operation.get("tags", ["Uncategorised"])[0]
            rows.append(
                f"| `{method.upper()}` | `{path}` | {operation.get('summary', '')} | {tag} |"
            )
    document = DOC.read_text(encoding="utf-8")
    before, marker_and_after = document.split(START, 1)
    _, after = marker_and_after.split(END, 1)
    generated = "\n".join(rows)
    DOC.write_text(f"{before}{START}\n{generated}\n{END}{after}", encoding="utf-8")


if __name__ == "__main__":
    main()
