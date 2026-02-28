import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock
import pyotp
from app.services.auth_service import AuthService
from app.core.config import Settings

@pytest.fixture
def mock_store():
    return MagicMock()

@pytest.fixture
def mock_repository():
    return MagicMock()

@pytest.fixture
def settings():
    return Settings(
        admin_mfa_required=True,
        admin_mfa_totp_secret="JBSWY3DPEHPK3PXP" # Base32 secret
    )

@pytest.fixture
def auth_service(settings, mock_repository):
    return AuthService(settings=settings, auth_repository=mock_repository)

def test_admin_login_with_valid_totp(auth_service, mock_repository, settings):
    user = {
        "id": "admin_1",
        "email": "admin@example.com",
        "name": "Admin User",
        "createdAt": "2026-01-01T00:00:00Z",
        "passwordHash": "hash",
        "role": "admin"
    }
    mock_repository.get_user_by_email.return_value = user
    
    # Generate valid TOTP
    totp = pyotp.TOTP(settings.admin_mfa_totp_secret)
    valid_otp = totp.now()
    
    # Mock password verification (assuming verify_password returns True for this test)
    with MagicMock() as mock_verify:
        import app.services.auth_service as auth_mod
        original_verify = auth_mod.verify_password
        auth_mod.verify_password = lambda p, h: True
        
        try:
            result = auth_service.login("admin@example.com", "password", otp=valid_otp)
            assert "accessToken" in result
        finally:
            auth_mod.verify_password = original_verify

def test_admin_login_with_invalid_totp(auth_service, mock_repository, settings):
    user = {
        "id": "admin_1",
        "email": "admin@example.com",
        "name": "Admin User",
        "createdAt": "2026-01-01T00:00:00Z",
        "passwordHash": "hash",
        "role": "admin"
    }
    mock_repository.get_user_by_email.return_value = user
    
    with MagicMock() as mock_verify:
        import app.services.auth_service as auth_mod
        original_verify = auth_mod.verify_password
        auth_mod.verify_password = lambda p, h: True
        
        try:
            with pytest.raises(HTTPException) as exc:
                auth_service.login("admin@example.com", "password", otp="000000")
            assert exc.value.status_code == 401
            assert "Invalid Admin OTP" in exc.value.detail
        finally:
            auth_mod.verify_password = original_verify

def test_customer_login_skips_totp(auth_service, mock_repository, settings):
    user = {
        "id": "user_1",
        "email": "user@example.com",
        "name": "Customer User",
        "createdAt": "2026-01-01T00:00:00Z",
        "passwordHash": "hash",
        "role": "customer"
    }
    mock_repository.get_user_by_email.return_value = user
    
    with MagicMock() as mock_verify:
        import app.services.auth_service as auth_mod
        original_verify = auth_mod.verify_password
        auth_mod.verify_password = lambda p, h: True
        
        try:
            result = auth_service.login("user@example.com", "password")
            assert "accessToken" in result
        finally:
            auth_mod.verify_password = original_verify
