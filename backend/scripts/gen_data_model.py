"""Generate a compact SQLAlchemy table/column reference."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Base

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "api" / "data-model-generated.md"


def render() -> str:
    lines = [
        "# Generated data model reference",
        "",
        "Do not edit; run `python backend/scripts/gen_data_model.py`.",
        "",
    ]
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        lines += [
            f"## `{table.name}`",
            "",
            "| Column | Type | Nullable | Key | Protection |",
            "|---|---|---:|---|---|",
        ]
        for column in table.columns:
            key = "PK" if column.primary_key else "FK" if column.foreign_keys else ""
            protection = (
                "Encrypted"
                if column.name.endswith("_encrypted")
                else "Hash"
                if column.name.endswith("_hash")
                else ""
            )
            lines.append(
                f"| `{column.name}` | `{column.type}` | {column.nullable} | {key} | {protection} |"
            )
        lines.append("")
    result = "\n".join(lines)
    return result


def generate() -> str:
    result = render()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result, encoding="utf-8")
    return result


if __name__ == "__main__":
    generate()
