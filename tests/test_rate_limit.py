from redis.exceptions import ConnectionError as RedisConnectionError

LOGIN_URL = "/users/login"
TOKEN_URL = "/users/token"
EMAIL = "user@example.com"
PASSWORD = "strongpass123"


async def register(client):
    resp = await client.post(
        "/users/register",
        json={"email": EMAIL, "username": "artem", "password": PASSWORD},
    )
    assert resp.status_code == 201


async def test_login_is_limited(client, login_limiter):
    login_limiter.limit = 3
    await register(client)

    statuses = [
        (await client.post(LOGIN_URL, json={"email": EMAIL, "password": "wrongpass123"})).status_code
        for _ in range(4)
    ]

    assert statuses == [401, 401, 401, 429]


async def test_429_has_retry_after(client, login_limiter):
    login_limiter.limit = 1
    await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})

    assert resp.status_code == 429
    assert resp.headers["retry-after"] == str(login_limiter.window_seconds)


async def test_limit_blocks_even_correct_password(client, login_limiter):
    """Otherwise an attacker could keep guessing and just watch for a 200."""
    login_limiter.limit = 2
    await register(client)
    for _ in range(2):
        await client.post(LOGIN_URL, json={"email": EMAIL, "password": "wrongpass123"})

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})

    assert resp.status_code == 429


async def test_form_login_shares_the_limit(client, login_limiter):
    login_limiter.limit = 2
    await client.post(LOGIN_URL, json={"email": EMAIL, "password": "wrongpass123"})
    await client.post(TOKEN_URL, data={"username": EMAIL, "password": "wrongpass123"})

    resp = await client.post(TOKEN_URL, data={"username": EMAIL, "password": "wrongpass123"})

    assert resp.status_code == 429


async def test_register_is_not_limited(client, login_limiter):
    login_limiter.limit = 1
    await client.post(LOGIN_URL, json={"email": EMAIL, "password": "wrongpass123"})
    await client.post(LOGIN_URL, json={"email": EMAIL, "password": "wrongpass123"})

    resp = await client.post(
        "/users/register",
        json={"email": "new@example.com", "username": "newuser", "password": PASSWORD},
    )

    assert resp.status_code == 201


async def test_fails_open_when_redis_is_down(client, login_limiter, monkeypatch):
    async def broken(*args, **kwargs):
        raise RedisConnectionError("Redis is down")

    monkeypatch.setattr(login_limiter.client, "set", broken)
    await register(client)

    resp = await client.post(LOGIN_URL, json={"email": EMAIL, "password": PASSWORD})

    assert resp.status_code == 200
