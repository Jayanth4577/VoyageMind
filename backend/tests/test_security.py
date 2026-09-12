from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("s3cret!")
    assert h != "s3cret!"
    assert verify_password("s3cret!", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    token = create_access_token("user-42")
    claims = decode_token(token)
    assert claims is not None
    assert claims["sub"] == "user-42"


def test_invalid_token_rejected():
    assert decode_token("not-a-jwt") is None
