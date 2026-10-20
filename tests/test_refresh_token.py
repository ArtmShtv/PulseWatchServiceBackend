from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.db.models.user import User

REGISTER_URL = "/users/register"
LOGIN_URL = "/users/login"  # поправьте под свой роутер
URL = "/users/refresh"      # поправьте под свой роутер

EMAIL = "user@example.com"
PASSWORD = "strongpass123"
INVALID = "Invalid refresh token"


def make_token(
    sub="1",
    token_type="refresh",
    expires_in=timedelta(days=7),
    key=None,
    algorithm=None,
    **extra,
):
    """Собирает токен вручную, чтобы проверять плохие варианты."""
    now = datetime.now(UTC)
    payload = {"type": token_type, "iat": now, "exp": now + expires_in} | extra
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(
        payload,
        key or settings.SECRET_KEY,
        algorithm=algorithm or settings.ALGORITHM,
    )


def decode(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


@pytest.fixture
async def registered(client):
    resp = await client.post(
        REGISTER_URL,
        json={"email": EMAIL, "username": "artem", "password": PASSWORD},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def tokens(client, registered):
    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    return resp.json()


async def test_refresh_success(client, registered, tokens):
    resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_refresh_returns_valid_access_token(client, registered, tokens):
    resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})

    payload = decode(resp.json()["access_token"])
    assert payload["type"] == "access"
    assert payload["sub"] == str(registered["id"])


async def test_refresh_does_not_return_new_refresh_token(client, registered, tokens):
    """Сейчас ротации нет. Если добавите ротацию, поменяйте этот тест."""
    resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})

    assert "refresh_token" not in resp.json()


async def test_refresh_can_be_used_repeatedly(client, registered, tokens):
    """Без ротации один refresh работает несколько раз."""
    for _ in range(2):
        resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200


async def test_refresh_rejects_access_token(client, registered, tokens):
    resp = await client.post(URL, json={"refresh_token": tokens["access_token"]})

    assert resp.status_code == 401


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c"])
async def test_refresh_rejects_garbage(client, registered, token):
    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_expired_token(client, registered):
    token = make_token(sub=str(registered["id"]), expires_in=timedelta(seconds=-10))

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_wrong_signature(client, registered):
    token = make_token(sub=str(registered["id"]), key="x" * 64)

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_alg_none(client, registered):
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(registered["id"]),
            "type": "refresh",
            "exp": now + timedelta(days=1),
        },
        key=None,
        algorithm="none",
    )

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_token_without_sub(client, registered):
    token = make_token(sub=None)

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_token_without_type(client, registered):
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(registered["id"]), "exp": now + timedelta(days=1)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


@pytest.mark.parametrize("sub", ["artem", "abc", "1.5", ""])
async def test_refresh_rejects_non_numeric_sub(client, registered, sub):
    """Токены старого формата (sub = username) не должны проходить."""
    resp = await client.post(URL, json={"refresh_token": make_token(sub=sub)})

    assert resp.status_code == 401


async def test_refresh_rejects_unknown_user_id(client, registered):
    token = make_token(sub="999999")

    resp = await client.post(URL, json={"refresh_token": token})

    assert resp.status_code == 401


async def test_refresh_rejects_inactive_user(client, session, registered, tokens):
    user = await session.get(User, registered["id"])
    user.is_active = False
    await session.commit()

    resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})

    assert resp.status_code == 401


async def test_refresh_rejects_deleted_user(client, session, registered, tokens):
    user = await session.get(User, registered["id"])
    await session.delete(user)
    await session.commit()

    resp = await client.post(URL, json={"refresh_token": tokens["refresh_token"]})

    assert resp.status_code == 401


async def test_refresh_errors_are_indistinguishable(client, registered, tokens):
    """Разные причины отказа не должны отличаться в ответе."""
    bad_tokens = [
        "garbage",
        tokens["access_token"],
        make_token(sub=str(registered["id"]), expires_in=timedelta(seconds=-10)),
        make_token(sub="999999"),
    ]

    responses = [
        await client.post(URL, json={"refresh_token": t}) for t in bad_tokens
    ]

    assert {r.status_code for r in responses} == {401}
    assert len({r.text for r in responses}) == 1


async def test_refresh_token_in_query_string_is_not_accepted(
    client, registered, tokens
):
    resp = await client.post(f"{URL}?refresh_token={tokens['refresh_token']}")

    assert resp.status_code == 422


async def test_refresh_missing_body(client):
    resp = await client.post(URL)

    assert resp.status_code == 422


async def test_refresh_missing_field(client):
    resp = await client.post(URL, json={})

    assert resp.status_code == 422