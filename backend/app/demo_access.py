import base64
import hashlib
import hmac
import time


SESSION_TTL_SECONDS = 12 * 60 * 60


def create_session_token(secret: str, now: int | None = None) -> str:
    expires_at = int(time.time() if now is None else now) + SESSION_TTL_SECONDS
    payload = base64.urlsafe_b64encode(str(expires_at).encode("ascii")).decode("ascii").rstrip("=")
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(token: str | None, secret: str, now: int | None = None) -> bool:
    if not token or len(token) > 128 or "." not in token:
        return False

    payload, signature = token.rsplit(".", 1)
    if (
        not payload
        or len(signature) != 64
        or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for character in payload)
        or any(character not in "0123456789abcdef" for character in signature)
    ):
        return False

    expected = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return False

    try:
        padding = "=" * (-len(payload) % 4)
        expires_at = int(base64.urlsafe_b64decode(payload + padding).decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        return False

    current_time = int(time.time() if now is None else now)
    return current_time < expires_at
