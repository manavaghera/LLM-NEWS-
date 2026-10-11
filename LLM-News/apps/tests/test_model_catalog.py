import json

import pytest
from fastapi import HTTPException

from app.api.endpoints.news import get_model_catalog


def test_model_catalog_is_served_only_with_a_valid_model_list(static_root):
    path = static_root / "static" / "model_catalog.json"
    path.write_text(json.dumps({"updated_at": "2026-10-10", "models": [{"id": "model-1"}]}), encoding="utf-8")
    assert get_model_catalog()["models"][0]["id"] == "model-1"

    path.write_text(json.dumps({"models": {}}), encoding="utf-8")
    with pytest.raises(HTTPException) as error:
        get_model_catalog()
    assert error.value.status_code == 500
