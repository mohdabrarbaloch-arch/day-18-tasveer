"""API tests: auth, generation, gallery, and the security boundaries."""

from app.main import app


def test_health_reports_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["styles"] >= 8
    assert "1:1" in body["aspect_ratios"]


def test_styles_endpoint_lists_presets(client):
    res = client.get("/api/styles")
    assert res.status_code == 200
    keys = {s["key"] for s in res.json()}
    assert {"cinematic", "cyberpunk", "watercolor", "minimal"} <= keys


def test_register_returns_token_and_credits(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "newbie@example.com",
            "display_name": "Newbie",
            "password": "hunter2abc",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["access_token"]
    assert body["user"]["credits"] == 60
    assert body["user"]["email"] == "newbie@example.com"


def test_register_rejects_duplicate_email(client, user_payload):
    client.post("/api/auth/register", json=user_payload)
    res = client.post("/api/auth/register", json=user_payload)
    assert res.status_code == 409


def test_register_rejects_weak_password(client):
    res = client.post(
        "/api/auth/register",
        json={
            "email": "weak@example.com",
            "display_name": "Weak",
            "password": "onlyletters",
        },
    )
    assert res.status_code == 422


def test_register_rejects_short_password(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "display_name": "S", "password": "a1"},
    )
    assert res.status_code == 422


def test_login_with_wrong_password_is_401(client, user_payload):
    client.post("/api/auth/register", json=user_payload)
    res = client.post(
        "/api/auth/login",
        json={"email": user_payload["email"], "password": "wrongpass1"},
    )
    assert res.status_code == 401


def test_login_unknown_email_is_401(client):
    res = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    assert res.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_current_user(client, auth_headers):
    res = client.get("/api/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "tester@example.com"


def test_generation_requires_auth(client):
    res = client.post("/api/generations", json={"prompt": "a cat"})
    assert res.status_code == 401


def test_generation_creates_four_images(client, auth_headers):
    res = client.post(
        "/api/generations",
        json={"prompt": "a quiet harbour at dawn", "style": "watercolor", "count": 4},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["images"]) == 4
    assert body["style"] == "watercolor"
    assert body["credits_spent"] == 1
    for img in body["images"]:
        assert img["url"].startswith("/media/")
        assert img["width"] > 0 and img["height"] > 0


def test_generation_charges_one_credit(client, auth_headers):
    before = client.get("/api/auth/me", headers=auth_headers).json()["credits"]
    client.post("/api/generations", json={"prompt": "a red fox"}, headers=auth_headers)
    after = client.get("/api/auth/me", headers=auth_headers).json()["credits"]
    assert after == before - 1


def test_generation_rejects_unknown_style(client, auth_headers):
    res = client.post(
        "/api/generations",
        json={"prompt": "a cat", "style": "not-a-style"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_generation_rejects_blank_prompt(client, auth_headers):
    res = client.post("/api/generations", json={"prompt": "   "}, headers=auth_headers)
    assert res.status_code == 422


def test_generation_rejects_bad_aspect_ratio(client, auth_headers):
    res = client.post(
        "/api/generations",
        json={"prompt": "a cat", "aspect_ratio": "7:3"},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_generation_rejects_oversized_count(client, auth_headers):
    res = client.post(
        "/api/generations",
        json={"prompt": "a cat", "count": 99},
        headers=auth_headers,
    )
    assert res.status_code == 422


def test_generation_is_reproducible_with_a_seed(client, auth_headers):
    payload = {"prompt": "a red fox in snow", "style": "minimal", "seed": 4242}
    first = client.post("/api/generations", json=payload, headers=auth_headers).json()
    second = client.post("/api/generations", json=payload, headers=auth_headers).json()

    assert first["seed"] == second["seed"] == 4242
    assert [i["seed"] for i in first["images"]] == [i["seed"] for i in second["images"]]


def test_media_file_is_served(client, auth_headers):
    gen = client.post(
        "/api/generations", json={"prompt": "a blue door"}, headers=auth_headers
    ).json()
    url = gen["images"][0]["url"]

    res = client.get(url)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) > 5_000


def test_history_lists_own_generations(client, auth_headers):
    client.post("/api/generations", json={"prompt": "a green field"}, headers=auth_headers)
    res = client.get("/api/generations", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_other_users_generation_is_404(client, auth_headers):
    gen = client.post(
        "/api/generations", json={"prompt": "private thing"}, headers=auth_headers
    ).json()

    other = client.post(
        "/api/auth/register",
        json={
            "email": "other@example.com",
            "display_name": "Other",
            "password": "otherpass1",
        },
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    res = client.get(f"/api/generations/{gen['id']}", headers=other_headers)
    assert res.status_code == 404


def test_delete_removes_generation(client, auth_headers):
    gen = client.post(
        "/api/generations", json={"prompt": "to be deleted"}, headers=auth_headers
    ).json()

    res = client.delete(f"/api/generations/{gen['id']}", headers=auth_headers)
    assert res.status_code == 204

    again = client.get(f"/api/generations/{gen['id']}", headers=auth_headers)
    assert again.status_code == 404


def test_public_generation_appears_in_gallery(client, auth_headers):
    client.post(
        "/api/generations",
        json={"prompt": "a shared sunset", "is_public": True},
        headers=auth_headers,
    )
    res = client.get("/api/gallery")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert any("shared sunset" in item["prompt"] for item in body["items"])


def test_private_generation_stays_out_of_gallery(client, auth_headers):
    client.post(
        "/api/generations",
        json={"prompt": "a secret garden", "is_public": False},
        headers=auth_headers,
    )
    res = client.get("/api/gallery")
    prompts = [item["prompt"] for item in res.json()["items"]]
    assert "a secret garden" not in prompts


def test_gallery_pagination_shape(client):
    res = client.get("/api/gallery?page=1&page_size=5")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"items", "total", "page", "page_size", "has_more"}


def test_security_headers_present(client):
    res = client.get("/api/health")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in res.headers


def test_invalid_token_is_401(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_stats_summary(client, auth_headers):
    client.post("/api/generations", json={"prompt": "stats test"}, headers=auth_headers)
    res = client.get("/api/generations/stats/summary", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["generations"] >= 1
    assert body["images"] >= 4
    assert "credits" in body


def test_openapi_schema_builds():
    """A broken schema means /docs is broken — catch it in CI."""
    schema = app.openapi()
    assert schema["info"]["title"].startswith("Tasveer")
    assert "/api/generations" in schema["paths"]
