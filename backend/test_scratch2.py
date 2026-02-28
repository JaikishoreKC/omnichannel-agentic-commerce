from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
register = client.post(
    "/v1/auth/register",
    json={
        "email": "orders-contract@example.com",
        "password": "SecurePass123!",
        "name": "Orders Contract",
    },
)
print(f"Status: {register.status_code}")
print(f"Response: {register.text}")
