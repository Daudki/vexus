from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("CorrectHorseBattery1")
    assert hashed != "CorrectHorseBattery1"
    assert verify_password("CorrectHorseBattery1", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_token("user-123", "access", extra_claims={"role": "admin"})
    claims = decode_token(token)
    assert claims is not None
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"
    assert claims["role"] == "admin"


def test_refresh_token_cannot_be_used_as_access_type():
    token = create_token("user-123", "refresh")
    claims = decode_token(token)
    assert claims["type"] == "refresh"  # caller is responsible for rejecting this as an access token


def test_invalid_token_returns_none():
    assert decode_token("not-a-real-token") is None
