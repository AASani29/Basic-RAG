"""The 5 required tests: register, login, unauthorized access, create item,
chat with no documents.

Async throughout, and asyncio_mode = "auto" (pyproject.toml) means no
@pytest.mark.asyncio needed on each one.
"""

from httpx import AsyncClient


async def test_register(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register", json={"email": "new@example.com", "password": "password123"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"
    assert "id" in body
    # The hash must never leave the API, under any field name.
    assert "hashed_password" not in body
    assert "password" not in body


async def test_login(client: AsyncClient) -> None:
    await client.post(
        "/auth/register", json={"email": "login@example.com", "password": "password123"}
    )
    r = await client.post(
        "/auth/login", data={"username": "login@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


async def test_unauthorized_access(client: AsyncClient) -> None:
    # No Authorization header at all — the earliest possible rejection point
    # (oauth2_scheme itself), before any route body or DB query runs.
    r = await client.get("/items")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


async def test_create_item(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    r = await client.post(
        "/items",
        json={"title": "Test Item", "description": "A test item"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Test Item"
    assert body["description"] == "A test item"
    assert body["owner_id"] is not None


async def test_chat_with_no_documents(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """This user has never uploaded a document, so answer_question's first
    short-circuit fires (a cheap COUNT, not an embedding call) and the
    response is the fixed no-context answer with no sources. Deterministic,
    and needs no Groq or embedding-model access — see conftest.py.
    """
    r = await client.post("/rag/chat", json={"question": "anything at all"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "I don't have anything in your documents about that."
    assert body["sources"] == []
