"""Generate the settings reference from the Pydantic settings class."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "api" / "config-generated.md"


def render() -> str:
    lines = [
        "# Generated configuration reference",
        "",
        "Do not edit; run `python backend/scripts/gen_config_docs.py`.",
        "",
        "| Setting | Type | Default |",
        "|---|---|---|",
    ]
    for name, field in Settings.model_fields.items():
        default = field.default if field.default is not None else "required"
        lines.append(f"| `{name}` | `{field.annotation}` | `{default}` |")
    result = "\n".join(lines) + "\n"
    return result


def generate() -> str:
    result = render()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(result, encoding="utf-8")
    return result


if __name__ == "__main__":
    generate()
