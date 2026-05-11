"""Tests for FastAPI routes with a fake CliRunner injected via dependency override."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from . import corpus
from .cli import CliInvocationError
from .main import create_app
from .routes import _runner_dep


class FakeRunner:
    """Test double exposing the same async surface as `CliRunner`.

    The dependency override doesn't care that this is not a real CliRunner — it
    only needs the awaitable methods that `routes.py` calls.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.version_response: dict[str, Any] = {
            "cli_version": "0.0.0",
            "embedding_model": "fake-emb",
            "latest_index_hash": "deadbeef",
        }
        self.index_list_response: list[dict[str, Any]] = [
            {"hash": "deadbeef", "model": "fake-emb", "dim": 8, "is_latest": True},
        ]
        self.query_response: dict[str, Any] = {
            "query": "test",
            "mode": "hybrid",
            "k": 1,
            "index": "deadbeef",
            "latency_ms": {"total": 10.0},
            "results": [
                {
                    "rank": 1,
                    "verse_id": "ether-12-6",
                    "ref": "Ether 12:6",
                    "text": "...",
                    "forced": False,
                    "score": 0.9,
                    "scores": {"bm25": 1.0, "dense": 0.95},
                },
            ],
        }
        self.feedback_response: dict[str, Any] = {"status": "recorded"}
        self.raise_with: Exception | None = None

    async def version(self) -> dict[str, Any]:
        self.calls.append(("version", {}))
        if self.raise_with is not None:
            raise self.raise_with
        return dict(self.version_response)

    async def index_list(self) -> list[dict[str, Any]]:
        self.calls.append(("index_list", {}))
        if self.raise_with is not None:
            raise self.raise_with
        return list(self.index_list_response)

    async def query(self, text: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("query", {"text": text, **kwargs}))
        if self.raise_with is not None:
            raise self.raise_with
        return dict(self.query_response)

    async def feedback(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("feedback", kwargs))
        if self.raise_with is not None:
            raise self.raise_with
        return dict(self.feedback_response)


@pytest.fixture
def fake_runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def client(fake_runner: FakeRunner) -> TestClient:
    app = create_app()
    app.dependency_overrides[_runner_dep] = lambda: fake_runner
    return TestClient(app)


@pytest.fixture
def fake_corpus_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Path]:
    bcbooks = tmp_path / "raw" / "bcbooks"
    bcbooks.mkdir(parents=True)
    bom = {
        "books": [
            {
                "book": "Alma",
                "chapters": [
                    {
                        "chapter": 32,
                        "verses": [
                            {"verse": 21, "reference": "Alma 32:21", "text": "faith is not…"},
                        ],
                    }
                ],
            }
        ]
    }
    (bcbooks / "book-of-mormon.json").write_text(json.dumps(bom))
    (bcbooks / "doctrine-and-covenants.json").write_text(json.dumps({"sections": []}))
    monkeypatch.setenv("SCRIPVEC_DATA_DIR", str(tmp_path))
    corpus.clear_cache()
    yield tmp_path
    corpus.clear_cache()


def test_get_version(client: TestClient, fake_runner: FakeRunner) -> None:
    resp = client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cli_version"] == "0.0.0"
    assert body["latest_index_hash"] == "deadbeef"
    assert fake_runner.calls[0][0] == "version"


def test_get_indexes(client: TestClient) -> None:
    resp = client.get("/api/indexes")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["hash"] == "deadbeef"


def test_post_query_passes_args(client: TestClient, fake_runner: FakeRunner) -> None:
    resp = client.post("/api/query", json={"text": "faith", "k": 7, "mode": "dense"})
    assert resp.status_code == 200
    name, args = fake_runner.calls[0]
    assert name == "query"
    assert args["text"] == "faith"
    assert args["k"] == 7
    assert args["mode"] == "dense"
    assert args["show_scores"] is True


def test_post_query_validates_mode(client: TestClient) -> None:
    resp = client.post("/api/query", json={"text": "x", "mode": "not-a-mode"})
    assert resp.status_code == 422


def test_post_query_requires_text(client: TestClient) -> None:
    resp = client.post("/api/query", json={"text": "", "k": 5})
    assert resp.status_code == 422


def test_post_feedback(client: TestClient, fake_runner: FakeRunner) -> None:
    resp = client.post(
        "/api/feedback",
        json={"query_id": "q1", "verse_id": "v1", "grade": 2, "note": "good"},
    )
    assert resp.status_code == 200
    name, args = fake_runner.calls[0]
    assert name == "feedback"
    assert args["grade"] == 2
    assert args["note"] == "good"


def test_post_feedback_rejects_bad_grade(client: TestClient) -> None:
    resp = client.post(
        "/api/feedback",
        json={"query_id": "q1", "verse_id": "v1", "grade": 9},
    )
    assert resp.status_code == 422


def test_cli_index_not_found_maps_to_404(client: TestClient, fake_runner: FakeRunner) -> None:
    fake_runner.raise_with = CliInvocationError(
        "missing", exit_code=2, payload={"error": "index_not_found"},
    )
    resp = client.post("/api/query", json={"text": "x"})
    assert resp.status_code == 404


def test_cli_user_error_maps_to_400(client: TestClient, fake_runner: FakeRunner) -> None:
    fake_runner.raise_with = CliInvocationError(
        "bad", exit_code=1, payload={"error": "bad_flag"},
    )
    resp = client.post("/api/query", json={"text": "x"})
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["error"] == "bad_flag"


def test_cli_upstream_error_maps_to_502(client: TestClient, fake_runner: FakeRunner) -> None:
    fake_runner.raise_with = CliInvocationError(
        "embed fail", exit_code=3, payload={"error": "embedding_endpoint"},
    )
    resp = client.post("/api/query", json={"text": "x"})
    assert resp.status_code == 502


def test_get_chapter(client: TestClient, fake_corpus_data: Path) -> None:
    resp = client.get("/api/chapter", params={"book": "Alma", "chapter": 32, "focus_verse": 21})
    assert resp.status_code == 200
    body = resp.json()
    assert body["book"] == "Alma"
    assert body["chapter"] == 32
    assert body["focus_verse"] == 21
    assert body["breadcrumb"] == "Alma › Chapter 32"  # noqa: RUF001
    assert body["verses"][0]["verse"] == 21


def test_get_chapter_404(client: TestClient, fake_corpus_data: Path) -> None:
    resp = client.get("/api/chapter", params={"book": "Not A Book", "chapter": 1})
    assert resp.status_code == 404


def test_get_books(client: TestClient, fake_corpus_data: Path) -> None:
    resp = client.get("/api/books")
    assert resp.status_code == 200
    body = resp.json()
    assert "Alma" in body
    assert body["Alma"] == [32]


def test_index_html_is_served(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ScripVec" in resp.text or "Scrip" in resp.text


def test_static_assets_served(client: TestClient) -> None:
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert "apiPost" in resp.text
