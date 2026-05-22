import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


class AuthError(Exception):
    pass


class AuthManager:
    def __init__(self):
        self._password_hasher = PasswordHasher()
        self.jwt_secret = os.getenv("JWT_SECRET", "replace-this-in-env")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_ttl_minutes = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15"))
        self.refresh_ttl_days = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))

    def hash_password(self, plain_password: str) -> str:
        return self._password_hasher.hash(plain_password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            return self._password_hasher.verify(password_hash, plain_password)
        except VerifyMismatchError:
            return False

    def _build_claims(self, user_id: int, username: str, token_type: str, expires_delta: timedelta) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        exp = now + expires_delta
        return {
            "sub": str(user_id),
            "username": username,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": str(uuid.uuid4()),
        }

    def create_access_token(self, user_id: int, username: str) -> str:
        claims = self._build_claims(
            user_id=user_id,
            username=username,
            token_type="access",
            expires_delta=timedelta(minutes=self.access_ttl_minutes),
        )
        return jwt.encode(claims, self.jwt_secret, algorithm=self.jwt_algorithm)

    def create_refresh_token(self, user_id: int, username: str) -> str:
        claims = self._build_claims(
            user_id=user_id,
            username=username,
            token_type="refresh",
            expires_delta=timedelta(days=self.refresh_ttl_days),
        )
        return jwt.encode(claims, self.jwt_secret, algorithm=self.jwt_algorithm)

    def decode_token(self, token: str, expected_type: str) -> Dict[str, Any]:
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
        except Exception as exc:
            raise AuthError(f"Invalid token: {exc}") from exc

        token_type = payload.get("type")
        if token_type != expected_type:
            raise AuthError("Invalid token type")
        return payload

    def refresh_expiry_iso(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=self.refresh_ttl_days)).isoformat()
