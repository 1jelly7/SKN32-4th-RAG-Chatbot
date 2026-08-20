# -*- coding: utf-8 -*-
"""FastAPI TestClient로 REST API 엔드포인트를 검증합니다."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.routers.api import router as legacy_router

client = TestClient(app)
legacy_app = FastAPI()
legacy_app.include_router(legacy_router)
legacy_client = TestClient(legacy_app)


def test_health_endpoint_returns_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"


def test_legacy_health_endpoint_exposes_backend_selection():
    res = legacy_client.get("/api/health")
    assert res.status_code == 200
    assert "embedding_backend" in res.json()


def test_fastapi_root_does_not_serve_django_owned_gui():
    res = client.get("/")
    assert res.status_code == 404


def test_prompts_list_endpoint():
    res = legacy_client.get("/api/prompts")
    assert res.status_code == 200
    assert isinstance(res.json()["prompts"], list)


def test_search_endpoint_validation_error_on_missing_query():
    res = legacy_client.post("/api/rag/search", json={})
    assert res.status_code == 422  # Pydantic 검증 오류


def test_files_endpoint_returns_list():
    res = legacy_client.get("/api/files")
    assert res.status_code == 200
    assert "files" in res.json()


def test_read_missing_file_returns_400():
    res = legacy_client.post("/api/files/read", json={"filename": "존재하지않는파일.pdf"})
    assert res.status_code == 400


def test_read_file_path_traversal_is_blocked():
    """docs 폴더 밖 파일에 접근하려는 시도는 차단되어야 합니다."""
    res = legacy_client.post("/api/files/read", json={"filename": "../../etc/passwd"})
    assert res.status_code == 400
