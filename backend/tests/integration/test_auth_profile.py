from fastapi.testclient import TestClient

from app.main import app


def test_profile_endpoints_require_authentication() -> None:
    client = TestClient(app)

    get_response = client.get("/v1/auth/profile")
    assert get_response.status_code == 401

    patch_response = client.patch("/v1/auth/profile", json={"phone": "+1 555 0100"})
    assert patch_response.status_code == 401


def test_profile_update_persists_and_marks_profile_complete() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "profile-flow@example.com",
            "password": "SecurePass123!",
            "name": "Profile User",
        },
    )
    assert register.status_code == 201
    assert register.json()["user"]["profileComplete"] is False
    access_token = register.json()["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    initial_profile = client.get("/v1/auth/profile", headers=headers)
    assert initial_profile.status_code == 200
    assert initial_profile.json()["user"]["profileComplete"] is False

    updated = client.patch(
        "/v1/auth/profile",
        json={
            "phone": "+1 555 0100",
            "timezone": "UTC",
            "defaultShippingAddress": {
                "name": "Profile User",
                "line1": "123 Commerce Street",
                "city": "Seattle",
                "state": "WA",
                "postalCode": "98101",
                "country": "US",
            },
        },
        headers=headers,
    )
    assert updated.status_code == 200
    updated_user = updated.json()["user"]
    assert updated_user["phone"] == "+1 555 0100"
    assert updated_user["profileComplete"] is True

    profile_after_update = client.get("/v1/auth/profile", headers=headers)
    assert profile_after_update.status_code == 200
    final_user = profile_after_update.json()["user"]
    assert final_user["profileComplete"] is True
    assert final_user["defaultShippingAddress"]["line1"] == "123 Commerce Street"


def test_profile_patch_preserves_omitted_fields() -> None:
    client = TestClient(app)

    register = client.post(
        "/v1/auth/register",
        json={
            "email": "profile-partial@example.com",
            "password": "SecurePass123!",
            "name": "Profile Partial",
        },
    )
    assert register.status_code == 201
    access_token = register.json()["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    seed = client.patch(
        "/v1/auth/profile",
        json={
            "phone": "+1 555 111 2222",
            "timezone": "UTC",
            "defaultShippingAddress": {
                "name": "Profile Partial",
                "line1": "10 Main St",
                "city": "Austin",
                "state": "TX",
                "postalCode": "78701",
                "country": "US",
            },
        },
        headers=headers,
    )
    assert seed.status_code == 200

    partial = client.patch(
        "/v1/auth/profile",
        json={
            "name": "Profile Partial Updated",
        },
        headers=headers,
    )
    assert partial.status_code == 200
    updated_user = partial.json()["user"]
    assert updated_user["name"] == "Profile Partial Updated"
    assert updated_user["phone"] == "+1 555 111 2222"
    assert updated_user["timezone"] == "UTC"
    assert updated_user["defaultShippingAddress"]["line1"] == "10 Main St"
