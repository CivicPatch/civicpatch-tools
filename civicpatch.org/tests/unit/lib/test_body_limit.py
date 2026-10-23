import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from lib.body_limit import PathBodyLimit

_LIMIT = 100


async def _echo_size(request: Request) -> PlainTextResponse:
    return PlainTextResponse(str(len(await request.body())))


def _client() -> TestClient:
    inner = Starlette(routes=[
        Route("/upload", _echo_size, methods=["POST"]),
        Route("/other", _echo_size, methods=["POST"]),
        Route("/uploads", _echo_size, methods=["POST"]),
        Route("/upload/drafts/1/rows", _echo_size, methods=["POST"]),
    ])
    return TestClient(PathBodyLimit(inner, path="/upload", max_body_size=_LIMIT))


def _chunks(total: int):
    """A streamed body: sent chunked, with no Content-Length to check up front."""
    for _ in range(total // 10):
        yield b"x" * 10


@pytest.mark.unit
def test_a_body_under_the_limit_reaches_the_route():
    response = _client().post("/upload", content=b"x" * _LIMIT)

    assert (response.status_code, response.text) == (200, str(_LIMIT))


@pytest.mark.unit
def test_a_declared_length_over_the_limit_is_refused():
    assert _client().post("/upload", content=b"x" * (_LIMIT + 1)).status_code == 413


@pytest.mark.unit
def test_a_chunked_body_over_the_limit_is_refused_though_it_declares_no_length():
    assert _client().post("/upload", content=_chunks(_LIMIT * 3)).status_code == 413


@pytest.mark.unit
def test_other_paths_are_not_limited():
    assert _client().post("/other", content=b"x" * (_LIMIT * 3)).status_code == 200


@pytest.mark.unit
def test_paths_under_the_limited_one_are_limited_too():
    assert _client().post("/upload/drafts/1/rows", content=b"x" * (_LIMIT * 3)).status_code == 413


@pytest.mark.unit
def test_a_path_that_only_starts_with_the_same_letters_is_not_limited():
    assert _client().post("/uploads", content=b"x" * (_LIMIT * 3)).status_code == 200
