"""Reject high-risk repository persistence and disguised executable patterns."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PATHS = {".env", ".vscode/tasks.json"}
EXECUTABLE_EXTENSIONS = {
    ".eot",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".orc",
    ".png",
    ".svg",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
}
CONTENT_RULES = {
    "automatic VS Code task execution": re.compile(
        rb'("task\.allowAutomaticTasks"\s*:\s*true|"runOn"\s*:\s*"folderOpen")'
    ),
    "known untrusted file-host URL": re.compile(rb"files\.catbox\.moe", re.IGNORECASE),
    "Node executing a disguised asset": re.compile(
        rb"\bnode(?:\.exe)?\s+[^\r\n;&|]+\.(?:eot|gif|ico|jpe?g|orc|png|svg|ttf|webp|woff2?)\b",
        re.IGNORECASE,
    ),
}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if not path.exists():
            continue
        if relative in FORBIDDEN_PATHS:
            findings.append(f"{relative}: forbidden tracked path")
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(f"{relative}: cannot inspect ({exc})")
            continue

        for label, pattern in CONTENT_RULES.items():
            if pattern.search(data):
                findings.append(f"{relative}: {label}")

        if path.suffix.lower() in EXECUTABLE_EXTENSIONS:
            if re.search(rb"\b(require\s*\(|eval\s*\(|Function\s*\()", data):
                findings.append(f"{relative}: executable code disguised as an asset")

    if findings:
        print("Security guard rejected the repository:", file=sys.stderr)
        for finding in findings:
            print(f"- {finding}", file=sys.stderr)
        return 1

    print("Security guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
