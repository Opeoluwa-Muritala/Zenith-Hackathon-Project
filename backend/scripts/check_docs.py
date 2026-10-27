"""Offline checks for documentation links, coverage and obvious secret leaks."""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.main import app

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")
INLINE_SETTING = re.compile(r"`([A-Z][A-Z0-9_]+)(?:=[^`]*)?`")
INLINE_PATH = re.compile(r"`(/[^`\s?]+)")
MERMAID = re.compile(r"```mermaid\s*\n\s*([^\s]+)")
SENSITIVE = [
    re.compile(r"Bearer\s+eyJ[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b(?:sk_live|live_sk)_[A-Za-z0-9]{8,}\b"),
    re.compile(r"(?<![0-9])[0-9]{11}(?![0-9])"),
]


def slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9 -]", "", value.lower()).replace(" ", "-"))


def route_exists(path: str, available: set[str]) -> bool:
    if path in available:
        return True
    for route in available:
        pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(route))
        if re.fullmatch(pattern, path):
            return True
    return False


def check() -> list[str]:
    errors = []
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    available = set(app.openapi()["paths"])
    setting_names = {name.upper() for name in Settings.model_fields}
    for path in DOCS.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(DOCS).as_posix()
        if path.name != "README.md" and relative not in index:
            errors.append(f"Unindexed docs file: {relative}")
        if path.suffix not in {".md", ".json"}:
            continue
        content = path.read_text(encoding="utf-8")
        for expression in SENSITIVE:
            if expression.search(content):
                errors.append(f"Secret-looking value: {relative}")
        if path.suffix != ".md":
            continue
        for match in LINK.finditer(content):
            target = unquote(match.group(1).split(" ", 1)[0].strip("<>"))
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            destination, _, anchor = target.partition("#")
            linked = (path.parent / destination).resolve() if destination else path
            if not linked.is_file():
                errors.append(f"Broken link: {relative} -> {target}")
            elif anchor and linked.suffix == ".md":
                headings = {
                    slug(line.lstrip("# ").strip())
                    for line in linked.read_text(encoding="utf-8").splitlines()
                    if line.startswith("#")
                }
                if anchor not in headings:
                    errors.append(f"Broken anchor: {relative} -> {target}")
        for match in MERMAID.finditer(content):
            if match.group(1) not in {
                "flowchart",
                "graph",
                "sequenceDiagram",
                "erDiagram",
                "classDiagram",
                "stateDiagram-v2",
                "gantt",
                "pie",
                "journey",
            }:
                errors.append(f"Invalid Mermaid type: {relative}")
        for name in INLINE_SETTING.findall(content):
            if "_" not in name and name not in setting_names:
                continue
            if path.name not in {
                "configuration.md",
                "api-guide.md",
                "api.md",
                "demo-mode.md",
                "getting-started.md",
                "mono-integration.md",
                "ai.md",
                "webhooks.md",
                "runbook.md",
                "authentication.md",
            }:
                continue
            if name not in setting_names and name not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "PK",
                "FK",
                "UUID",
                "NGN",
                "USD",
                "UTC",
                "HMAC",
                "JWT",
                "OTP",
                "BVN",
                "NDPA",
                "API",
            }:
                errors.append(f"Unknown setting: {relative} -> {name}")
        if path.name in {
            "api-guide.md",
            "authentication.md",
            "getting-started.md",
            "webhooks.md",
            "demo-mode.md",
        }:
            for route in INLINE_PATH.findall(content):
                if route.startswith(("/docs", "/redoc", "/dev/", "/v2/", "/v3/")):
                    continue
                if not route_exists(route, available):
                    errors.append(f"Unknown API path: {relative} -> {route}")
    return errors


if __name__ == "__main__":
    findings = check()
    for finding in findings:
        print(finding)
    if findings:
        raise SystemExit(1)
    print("Documentation checks passed")
