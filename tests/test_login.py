import jwt
import pytest

from app.core.security import hash_password, verify_password

REGISTER_URL = "/users/register"
URL = "/users/login" 

EMAIL = "user@example.com"
PASSWORD = "strongpass123"
INVALID = "Incorrect email or password"


def payload(**overrides):
    data = {"email": EMAIL, "password": PASSWORD}
    return data | overrides


@pytest.fixture
async def registered(client):
    """Создаём пользователя через реальный эндпоинт регистрации."""
    resp = await client.post(
        REGISTER_URL,
        json={"email": EMAIL, "username": "artem", "password": PASSWORD},
    )
    assert resp.status_code == 201
    return resp.json()


def decode(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


async def test_login_success(client, registered):
    resp = await client.post(URL, json=payload())

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]
    assert "password" not in body


async def test_login_tokens_payload(client, registered):
    body = (await client.post(URL, json=payload())).json()

    access = decode(body["access_token"])
    refresh = decode(body["refresh_token"])
    assert access["sub"] == refresh["sub"]
    assert access["exp"] < refresh["exp"]


async def test_login_normalizes_email(client, registered):
    resp = await client.post(URL, json=payload(email="  USER@Example.COM "))

    assert resp.status_code == 200


async def test_login_wrong_password(client, registered):
    resp = await client.post(URL, json=payload(password="wrongpass123"))

    assert resp.status_code == 401
    assert resp.json()["detail"] == INVALID
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_login_unknown_email(client, registered):
    resp = await client.post(URL, json=payload(email="nobody@example.com"))

    assert resp.status_code == 401
    assert resp.json()["detail"] == INVALID


async def test_login_no_users_in_db(client):
    resp = await client.post(URL, json=payload())

    assert resp.status_code == 401


async def test_login_errors_are_indistinguishable(client, registered):
    """Защита от user enumeration: ответы совпадают полностью."""
    wrong_pass = await client.post(URL, json=payload(password="wrongpass123"))
    no_user = await client.post(URL, json=payload(email="nobody@example.com"))

    assert wrong_pass.status_code == no_user.status_code
    assert wrong_pass.json() == no_user.json()


async def test_login_password_is_case_sensitive(client, registered):
    resp = await client.post(URL, json=payload(password=PASSWORD.upper()))

    assert resp.status_code == 401


async def test_login_verifies_password_even_if_user_not_found(client, monkeypatch):
    from app.services import auth_services as auth_module

    calls = []
    original = auth_module.verify_password

    def spy(password, hashed):
        calls.append(hashed)
        return original(password, hashed)

    monkeypatch.setattr(auth_module, "verify_password", spy)

    resp = await client.post(URL, json=payload(email="nobody@example.com"))

    assert resp.status_code == 401
    assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"password": ""},
        {"password": "x" * 129},
    ],
)
async def test_login_validation_errors(client, override):
    resp = await client.post(URL, json=payload(**override))

    assert resp.status_code == 422


@pytest.mark.parametrize("missing", ["email", "password"])
async def test_login_missing_field(client, missing):
    data = payload()
    del data[missing]

    resp = await client.post(URL, json=data)

    assert resp.status_code == 422


async def test_login_non_json_body(client):
    resp = await client.post(URL, content="not json")

    assert resp.status_code == 422


# ---------- хеширование (юнит) ----------
# test_verify_password_accepts_correct на текущем коде упадёт:
# это баг с двойным хешированием в verify_password.

def test_verify_password_accepts_correct():
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_verify_password_rejects_wrong():
    assert verify_password("wrongpass123", hash_password(PASSWORD)) is False


def test_hash_is_salted_and_not_plaintext():
    h1, h2 = hash_password(PASSWORD), hash_password(PASSWORD)

    assert h1 != h2
    assert PASSWORD not in h1