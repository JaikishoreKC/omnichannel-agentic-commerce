from app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
register = client.post("/v1/auth/register", json={"email": "a", "password": "b", "name": "c"})
print(f"Status: {register.status_code}")
print(f"Response: {register.text}")
