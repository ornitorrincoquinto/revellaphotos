from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import jwt, JWTError

from .config import settings


def _prepare(password: str) -> bytes:
    # bcrypt só considera os primeiros 72 bytes de qualquer senha — isso é uma
    # limitação do próprio algoritmo, não do nosso código.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_prepare(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, role: str = "photographer") -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token_payload(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[str]:
    """Mantido por compatibilidade: devolve só o 'sub' (usado pelo fluxo de fotógrafo)."""
    payload = decode_token_payload(token)
    return payload.get("sub") if payload else None
