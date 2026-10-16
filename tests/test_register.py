import pytest
from sqlalchemy import select

from app.db.models.user import User

URL = "/users/register"


def payload(**overrides):
    data = {
        "email": "user@example.com",
        "username": "artem",
        "password": "strongpass123",
    }
    return data | overrides


async def test_register_success(client, session):
    resp = await client.post(URL, json=payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "user@example.com"
    assert body["username"] == "artem"
    assert "id" in body
    assert "password" not in body

    user = (await session.execute(select(User))).scalar_one()
    assert user.password != "strongpass123" 


async def test_register_normalizes_case(client, session):
    resp = await client.post(
        URL, json=payload(email="User@Example.COM", username="  ArTeM ")
    )

    assert resp.status_code == 201
    assert resp.json()["email"] == "user@example.com"
    assert resp.json()["username"] == "artem"


async def test_register_duplicate_email(client):
    await client.post(URL, json=payload())

    resp = await client.post(URL, json=payload(username="other"))

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Email or username already exists"


async def test_register_duplicate_username(client):
    await client.post(URL, json=payload())

    resp = await client.post(URL, json=payload(email="other@example.com"))

    assert resp.status_code == 409


async def test_register_duplicate_is_case_insensitive(client):
    await client.post(URL, json=payload())

    resp = await client.post(URL, json=payload(email="USER@example.com"))

    assert resp.status_code == 409


async def test_register_email_and_username_from_different_users(client):
    await client.post(URL, json=payload(email="a@example.com", username="aaa"))
    await client.post(URL, json=payload(email="b@example.com", username="bbb"))

    resp = await client.post(URL, json=payload(email="a@example.com", username="bbb"))

    assert resp.status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"email": "not-an-email"},
        {"username": "ab"},
        {"username": "a" * 51},
        {"password": "short"}, 
        {"password": "x" * 129},
    ],
)
async def test_register_validation_errors(client, override):
    resp = await client.post(URL, json=payload(**override))

    assert resp.status_code == 422


async def test_register_missing_field(client):
    data = payload()
    del data["password"]

    resp = await client.post(URL, json=data)

    assert resp.status_code == 422