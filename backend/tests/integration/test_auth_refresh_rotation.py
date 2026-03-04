from fastapi.testclient import TestClient

from app.main import app


def test_refresh_token_rotation_revokes_previous_token() -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "rotation@example.com",
            "password": "SecurePass123!",
            "name": "Rotation User",
        },
    )
    assert register.status_code == 201
    first_refresh = register.json()["refreshToken"]

    refreshed = client.post("/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert refreshed.status_code == 200
    second_refresh = refreshed.json()["refreshToken"]
    assert second_refresh != first_refresh

    reused = client.post("/v1/auth/refresh", json={"refreshToken": first_refresh})
    assert reused.status_code == 401

    second = client.post("/v1/auth/refresh", json={"refreshToken": second_refresh})
    assert second.status_code == 200


def test_logout_revokes_cookie_refresh_token_and_clears_auth_cookies() -> None:
    client = TestClient(app)
    register = client.post(
        "/v1/auth/register",
        json={
            "email": "logout@example.com",
            "password": "SecurePass123!",
            "name": "Logout User",
        },
    )
    assert register.status_code == 201

    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 204

    set_cookie_headers = logout.headers.get_list("set-cookie")
    assert any(header.startswith("access_token=") for header in set_cookie_headers)
    assert any(header.startswith("refresh_token=") for header in set_cookie_headers)

    refreshed = client.post("/v1/auth/refresh", json={})
    assert refreshed.status_code == 401

