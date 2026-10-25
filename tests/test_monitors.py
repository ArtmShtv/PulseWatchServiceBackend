import pytest

REGISTER_URL = "/users/register"
LOGIN_URL = "/users/login"
URL = "/monitors/"

PASSWORD = "strongpass123"


def monitor_payload(**overrides):
    data = {
        "name": "Example",
        "url": "https://example.com",
        "interval_seconds": 60,
        "timeout_seconds": 10,
    }
    return data | overrides


async def auth_headers(client, email="user@example.com", username="artem"):
    resp = await client.post(
        REGISTER_URL,
        json={"email": email, "username": username, "password": PASSWORD},
    )
    assert resp.status_code == 201
    resp = await client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
async def headers(client):
    return await auth_headers(client)


@pytest.fixture
async def monitor(client, headers):
    resp = await client.post(URL, json=monitor_payload(), headers=headers)
    assert resp.status_code == 201
    return resp.json()


# ---------- auth ----------

async def test_requires_auth(client):
    resp = await client.get(URL)

    assert resp.status_code == 401


# ---------- create ----------

async def test_create_monitor(client, headers):
    resp = await client.post(URL, json=monitor_payload(), headers=headers)

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Example"
    assert body["url"] == "https://example.com/"
    assert body["current_status"] is None


async def test_create_duplicate_returns_409(client, headers, monitor):
    resp = await client.post(URL, json=monitor_payload(name="Other"), headers=headers)

    assert resp.status_code == 409


async def test_create_timeout_must_be_less_than_interval(client, headers):
    resp = await client.post(
        URL, json=monitor_payload(interval_seconds=60, timeout_seconds=60), headers=headers
    )

    assert resp.status_code == 422


async def test_list_only_own_monitors(client, headers, monitor):
    other = await auth_headers(client, email="other@example.com", username="other")
    await client.post(URL, json=monitor_payload(url="https://other.com"), headers=other)

    resp = await client.get(URL, headers=headers)

    assert resp.status_code == 200
    assert [m["id"] for m in resp.json()] == [monitor["id"]]


async def test_get_monitor(client, headers, monitor):
    resp = await client.get(f"{URL}{monitor['id']}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["id"] == monitor["id"]


async def test_get_missing_monitor_returns_404(client, headers):
    resp = await client.get(f"{URL}999999", headers=headers)

    assert resp.status_code == 404


async def test_cannot_get_other_users_monitor(client, monitor):
    other = await auth_headers(client, email="other@example.com", username="other")

    resp = await client.get(f"{URL}{monitor['id']}", headers=other)

    assert resp.status_code == 404


async def test_update_name(client, headers, monitor):
    resp = await client.patch(f"{URL}{monitor['id']}", json={"name": "New"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


async def test_update_url_is_stored_as_string(client, headers, monitor):
    resp = await client.patch(
        f"{URL}{monitor['id']}", json={"url": "https://new.example.com"}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://new.example.com/"


async def test_update_empty_body_returns_422(client, headers, monitor):
    resp = await client.patch(f"{URL}{monitor['id']}", json={}, headers=headers)

    assert resp.status_code == 422


async def test_update_null_field_is_ignored(client, headers, monitor):
    resp = await client.patch(
        f"{URL}{monitor['id']}", json={"name": None, "interval_seconds": 120}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Example"
    assert resp.json()["interval_seconds"] == 120


async def test_update_timeout_checked_against_existing_interval(client, headers, monitor):
    resp = await client.patch(
        f"{URL}{monitor['id']}", json={"timeout_seconds": 60}, headers=headers
    )

    assert resp.status_code == 422


async def test_update_to_duplicate_url_returns_409(client, headers, monitor):
    second = await client.post(
        URL, json=monitor_payload(url="https://second.com"), headers=headers
    )

    resp = await client.patch(
        f"{URL}{second.json()['id']}", json={"url": "https://example.com"}, headers=headers
    )

    assert resp.status_code == 409


async def test_cannot_update_other_users_monitor(client, monitor):
    other = await auth_headers(client, email="other@example.com", username="other")

    resp = await client.patch(f"{URL}{monitor['id']}", json={"name": "Hacked"}, headers=other)

    assert resp.status_code == 404


async def test_delete_monitor(client, headers, monitor):
    resp = await client.delete(f"{URL}{monitor['id']}", headers=headers)

    assert resp.status_code == 204
    assert resp.content == b""
    assert (await client.get(f"{URL}{monitor['id']}", headers=headers)).status_code == 404


async def test_delete_missing_monitor_returns_404(client, headers):
    resp = await client.delete(f"{URL}999999", headers=headers)

    assert resp.status_code == 404


async def test_cannot_delete_other_users_monitor(client, monitor):
    other = await auth_headers(client, email="other@example.com", username="other")

    resp = await client.delete(f"{URL}{monitor['id']}", headers=other)

    assert resp.status_code == 404