"""Generated API and reference artifacts must match the current application."""

import json
import re

import yaml

from app.main import app
from scripts.check_docs import check as check_docs
from scripts.export_openapi import BACKEND_OUTPUT
from scripts.export_openapi import OUTPUT as OPENAPI_OUTPUT
from scripts.export_postman import OUTPUT as POSTMAN_OUTPUT
from scripts.export_postman import build_postman
from scripts.gen_config_docs import OUTPUT as CONFIG_OUTPUT
from scripts.gen_config_docs import render as render_config
from scripts.gen_data_model import OUTPUT as MODEL_OUTPUT
from scripts.gen_data_model import render as render_model


def test_openapi_artifact_is_current():
    expected = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    assert OPENAPI_OUTPUT.read_text(encoding="utf-8") == expected, (
        "Run python backend/scripts/export_openapi.py"
    )
    assert BACKEND_OUTPUT.read_text(encoding="utf-8") == expected, (
        "Run python backend/scripts/export_openapi.py"
    )
    assert (
        yaml.safe_load(OPENAPI_OUTPUT.with_suffix(".yaml").read_text(encoding="utf-8"))
        == app.openapi()
    )


def test_postman_artifact_is_current_and_covers_each_operation_once():
    spec = app.openapi()
    expected = json.dumps(build_postman(spec), indent=2, sort_keys=True) + "\n"
    assert POSTMAN_OUTPUT.read_text(encoding="utf-8") == expected, (
        "Run python backend/scripts/export_postman.py"
    )
    operations = {
        (method.upper(), path)
        for path, methods in spec["paths"].items()
        for method in methods
        if method in {"get", "post", "put", "patch", "delete"}
    }
    collection = json.loads(expected)
    requests = [
        (
            item["request"]["method"],
            re.sub(
                r"\{\{([^{}]+)\}\}",
                lambda match: "{" + match.group(1) + "}",
                item["request"]["url"]["raw"].removeprefix("{{base_url}}"),
            ),
        )
        for folder in collection["item"]
        for item in folder["item"]
    ]
    assert len(requests) == len(set(requests)) == len(operations)
    assert set(requests) == operations


def test_model_and_settings_references_are_current():
    assert MODEL_OUTPUT.read_text(encoding="utf-8") == render_model(), (
        "Run python backend/scripts/gen_data_model.py"
    )
    assert CONFIG_OUTPUT.read_text(encoding="utf-8") == render_config(), (
        "Run python backend/scripts/gen_config_docs.py"
    )


def test_documentation_links_and_secret_hygiene():
    assert check_docs() == [], "Run python backend/scripts/check_docs.py"
