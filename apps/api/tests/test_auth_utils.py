from __future__ import annotations

from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    generate_2fa_code,
    hash_2fa_code,
)


class TestPasswordHashing:
    def test_hash_password(self):
        hashed = hash_password("testpass123")
        assert hashed != "testpass123"
        assert len(hashed) > 0

    def test_verify_password_success(self):
        hashed = hash_password("testpass123")
        assert verify_password("testpass123", hashed) is True

    def test_verify_password_failure(self):
        hashed = hash_password("testpass123")
        assert verify_password("wrongpass", hashed) is False


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_token_success(self):
        token = create_access_token({"sub": "user123", "user_id": "user123"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["user_id"] == "user123"
        assert payload["type"] == "access"

    def test_verify_token_invalid(self):
        payload = verify_token("invalid.token.here")
        assert payload is None

    def test_create_refresh_token(self):
        token, token_hash = create_refresh_token({"sub": "user123"})
        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token) > 0
        assert len(token_hash) > 0

        # Verify the token
        payload = verify_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"


class Test2FACodes:
    def test_generate_2fa_code(self):
        code = generate_2fa_code()
        assert isinstance(code, str)
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_2fa_code_uniqueness(self):
        codes = {generate_2fa_code() for _ in range(100)}
        # Very unlikely to have collisions, but not impossible
        assert len(codes) > 50  # At least 50 unique codes

    def test_hash_2fa_code(self):
        code = "123456"
        hashed = hash_2fa_code(code)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != code

        # Same code produces same hash
        hashed2 = hash_2fa_code(code)
        assert hashed == hashed2

        # Different codes produce different hashes
        hashed3 = hash_2fa_code("654321")
        assert hashed != hashed3
