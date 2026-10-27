"""Convert committed OpenAPI JSON to a secret-free Postman v2.1 collection."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs" / "api" / "openapi.json"
OUTPUT = ROOT / "docs" / "api" / "postman" / "fetch.postman_collection.json"
TAG_ORDER = [
    "Auth",
    "Onboarding",
    "Identity",
    "Consents",
    "Accounts and linking",
    "Assets",
    "Category rules",
    "Sync and statements",
    "Transactions",
    "Analytics",
    "Budget",
    "Obligations",
    "Notifications",
    "Summary",
    "Recurring",
    "Insights",
    "Forecast",
    "AI",
    "Webhooks",
    "Health",
]
VARIABLES = [
    "base_url",
    "access_token",
    "refresh_token",
    "otp_code",
    "test_bvn",
    "mono_webhook_secret",
    "link_ref",
    "session_id",
    "account_id",
    "transaction_id",
    "asset_id",
    "consent_id",
    "row_id",
    "obligation_id",
    "rule_id",
    "device_id",
    "insight_id",
    "conversation_id",
]


def _resolve(schema: dict, spec: dict) -> dict:
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        return _resolve(spec["components"]["schemas"][name], spec)
    if "anyOf" in schema:
        choices = [item for item in schema["anyOf"] if item.get("type") != "null"]
        return _resolve(choices[0], spec) if choices else {}
    return schema


def _example(schema: dict, spec: dict, name: str = ""):
    schema = _resolve(schema, spec)
    if name == "bvn":
        return "{{test_bvn}}"
    if name == "otp":
        return "{{otp_code}}"
    if name == "refresh_token":
        return "{{refresh_token}}"
    if name == "ref":
        return "{{link_ref}}"
    if name == "ids":
        return ["{{row_id}}"]
    if name.endswith("_id"):
        return "{{" + name + "}}"
    if "example" in schema:
        return schema["example"]
    if "examples" in schema and schema["examples"]:
        return schema["examples"][0]
    if schema.get("type") == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        if not properties and isinstance(schema.get("additionalProperties"), dict):
            key = (schema.get("propertyNames", {}).get("enum") or ["NGN"])[0]
            return {key: _example(schema["additionalProperties"], spec)}
        result = {key: _example(properties[key], spec, key) for key in sorted(properties)}
        if "phone" in result and "email" in result:
            result.pop("phone")
        if "method" in result and result["method"] != "alternate_phone":
            result.pop("phone_number", None)
        return result
    if schema.get("type") == "array":
        return [_example(schema.get("items", {}), spec, name)]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if schema.get("format") == "email" or name == "email":
        return "user@example.com"
    if schema.get("format") == "date-time":
        return "2026-01-01T00:00:00Z"
    if schema.get("format") == "date":
        return "2026-10-17"
    if schema.get("format") == "uuid":
        return "00000000-0000-4000-8000-000000000001"
    if schema.get("type") in {"integer", "number"}:
        return schema.get("minimum", 1)
    if schema.get("type") == "boolean":
        return False
    return ("fake_demo_value_" * 30)[: schema.get("minLength", 7)]


def _request(path: str, method: str, operation: dict, spec: dict) -> dict:
    raw_path = re.sub(r"\{([^{}]+)\}", lambda m: "{{" + m.group(1) + "}}", path)
    params = [
        {
            "key": p["name"],
            "value": str(_example(p.get("schema", {}), spec, p["name"])),
            "description": p.get("description", ""),
            "disabled": not p.get("required", False),
        }
        for p in operation.get("parameters", [])
        if p.get("in") == "query"
    ]
    url = {
        "raw": "{{base_url}}" + raw_path,
        "host": ["{{base_url}}"],
        "path": [
            re.sub(r"\{([^{}]+)\}", lambda m: "{{" + m.group(1) + "}}", p)
            for p in path.strip("/").split("/")
        ],
    }
    if params:
        url["query"] = params
    request = {
        "method": method.upper(),
        "header": [],
        "description": operation.get("description", ""),
        "url": url,
    }
    if not operation.get("security"):
        request["auth"] = {"type": "noauth"}
    media = operation.get("requestBody", {}).get("content", {})
    if "application/json" in media:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        body_schema = media["application/json"].get("schema", {})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(_example(body_schema, spec), indent=2),
            "options": {"raw": {"language": "json"}},
        }
    if path == "/webhooks/mono":
        request["header"].extend(
            [
                {"key": "Content-Type", "value": "application/json"},
                {"key": "mono-webhook-secret", "value": "{{mono_webhook_secret}}"},
            ]
        )
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(
                {
                    "event": "mono.events.account_connected",
                    "data": {
                        "id": "acc_fake",
                        "meta": {"ref": "{{link_ref}}", "data_status": "PROCESSING"},
                    },
                },
                indent=2,
            ),
            "options": {"raw": {"language": "json"}},
        }
    responses = []
    for code, definition in sorted(operation.get("responses", {}).items()):
        if not code.isdigit():
            continue
        example = definition.get("content", {}).get("application/json", {}).get("example")
        if example is None:
            response_schema = (
                definition.get("content", {}).get("application/json", {}).get("schema", {})
            )
            example = (
                _example(response_schema, spec)
                if int(code) < 400
                else {"detail": definition.get("description", "Error")}
            )
        responses.append(
            {
                "name": definition.get("description", code),
                "originalRequest": {"method": method.upper(), "url": url},
                "status": definition.get("description", ""),
                "code": int(code),
                "_postman_previewlanguage": "json",
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "body": "" if int(code) == 204 else json.dumps(example, indent=2),
            }
        )
    success = [
        int(code) for code in operation.get("responses", {}) if code.isdigit() and int(code) < 400
    ]
    assertion = (
        "pm.test('documented success', function () { "
        f"pm.expect({json.dumps(success)}).to.include(pm.response.code); "
        "});"
    )
    script = [assertion]
    if path in {"/auth/otp/verify", "/auth/refresh"}:
        script.append(
            "if (pm.response.code === 200) { const body = pm.response.json(); "
            "pm.collectionVariables.set('access_token', body.access_token); "
            "pm.collectionVariables.set('refresh_token', body.refresh_token); }"
        )
    if path == "/onboarding/bvn/start":
        script.append(
            "if (pm.response.code === 200) "
            "pm.collectionVariables.set('session_id', pm.response.json().session_id);"
        )
    if path == "/onboarding/bvn/confirm":
        script.append(
            "if (pm.response.code === 200) { const rows = pm.response.json(); "
            "if (rows.length) pm.collectionVariables.set('row_id', rows[0].id); }"
        )
    if path in {
        "/accounts/link/initiate",
        "/accounts/discovered/{row_id}/link",
        "/accounts/skipped/{row_id}/link",
    }:
        script.append(
            "if (pm.response.code < 300) "
            "pm.collectionVariables.set('link_ref', pm.response.json().ref);"
        )
    if path == "/accounts/link/status":
        script.append(
            "if (pm.response.code === 200 && pm.response.json().account_id) "
            "pm.collectionVariables.set('account_id', pm.response.json().account_id);"
        )
    if path == "/transactions" and method == "get":
        script.append(
            "if (pm.response.code === 200) { const rows = pm.response.json(); "
            "if (rows.length) pm.collectionVariables.set('transaction_id', rows[0].id); }"
        )
    if method.lower() == "post" and path in {
        "/assets",
        "/accounts/link",
        "/consents",
        "/obligations",
        "/devices",
    }:
        capture = (
            "asset_id"
            if path == "/assets"
            else "consent_id"
            if path == "/consents"
            else "obligation_id"
            if path == "/obligations"
            else "device_id"
            if path == "/devices"
            else "account_id"
        )
        script.append(
            "if (pm.response.code >= 200 && pm.response.code < 300) { "
            "const body = pm.response.json(); "
            f"if (body.id) pm.collectionVariables.set('{capture}', body.id); }}"
        )
    return {
        "name": operation.get("summary") or f"{method.upper()} {path}",
        "request": request,
        "response": responses,
        "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": script}}],
    }


def build_postman(spec: dict) -> dict:
    folders: dict[str, list] = {}
    flow = [
        "/health",
        "/auth/otp/request",
        "/auth/otp/verify",
        "/auth/refresh",
        "/auth/logout",
        "/auth/logout-all",
        "/onboarding/bvn/start",
        "/onboarding/bvn/send-otp",
        "/onboarding/bvn/confirm",
        "/accounts/discovered/select",
        "/accounts/discovered/{row_id}/link",
        "/accounts/link/initiate",
        "/accounts/link/status",
        "/accounts",
        "/accounts/{account_id}",
    ]
    for path in sorted(
        spec.get("paths", {}),
        key=lambda path: (flow.index(path) if path in flow else len(flow), path),
    ):
        for method, operation in sorted(spec["paths"][path].items()):
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = (operation.get("tags") or ["Other"])[0]
            if path == "/webhooks/mono":
                tag = "Webhooks (manual testing)"
            folders.setdefault(tag, []).append(_request(path, method, operation, spec))

    def order(tag: str):
        return (TAG_ORDER.index(tag) if tag in TAG_ORDER else len(TAG_ORDER), tag)

    return {
        "info": {
            "name": "Fetch API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}],
        },
        "variable": [
            {
                "key": key,
                "value": "http://localhost:8000" if key == "base_url" else "",
                "type": "string",
            }
            for key in VARIABLES
        ],
        "item": [{"name": tag, "item": folders[tag]} for tag in sorted(folders, key=order)],
    }


def export_postman() -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    collection = build_postman(spec)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(collection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return collection


if __name__ == "__main__":
    export_postman()
