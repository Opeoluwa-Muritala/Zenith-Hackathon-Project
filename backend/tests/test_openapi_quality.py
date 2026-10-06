from fastapi.testclient import TestClient

from app.main import OPENAPI_TAGS, app


def test_operations_have_stable_swagger_metadata_and_declared_journey_tags():
    schema = app.openapi()
    declared = {item["name"] for item in OPENAPI_TAGS}
    used_ids = set()
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete", "options", "head"}:
                continue
            assert operation.get("summary"), (method, path)
            assert operation.get("description"), (method, path)
            assert operation.get("operationId"), (method, path)
            assert operation["operationId"] not in used_ids
            used_ids.add(operation["operationId"])
            assert len(operation.get("tags", [])) == 1, (method, path)
            assert operation["tags"][0] in declared, (method, path)
            assert operation.get("responses"), (method, path)
            if path != "/health":
                assert any(code.startswith("4") for code in operation["responses"]), (method, path)


def test_openapi_does_not_expose_provider_secrets_or_internal_hashes():
    schema = app.openapi()
    denied = {"provider_account_id", "token_hash", "bvn_hash", "mono_secret_key"}
    for component in schema.get("components", {}).get("schemas", {}).values():
        assert denied.isdisjoint(component.get("properties", {}))


def test_ai_chat_security_scheme_is_bearer_auth():
    schema = app.openapi()
    chat = schema["paths"]["/ai/chat"]["post"]
    assert chat.get("security")
    assert "HTTPBearer" in schema["components"]["securitySchemes"]


def test_mono_test_page_is_loopback_only_and_not_in_public_schema():
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 43120)) as local:
        response = local.get("/dev/mono-test")
        assert response.status_code == 200
        assert "Test the account-link journey" in response.text
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert "localStorage" not in response.text
    with TestClient(app, base_url="http://203.0.113.10", client=("203.0.113.10", 43120)) as remote:
        assert remote.get("/dev/mono-test").status_code == 404
    with TestClient(app, base_url="http://attacker.test", client=("127.0.0.1", 43120)) as rebinding:
        assert rebinding.get("/dev/mono-test").status_code == 404
    assert "/dev/mono-test" not in app.openapi()["paths"]
