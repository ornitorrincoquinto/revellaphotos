from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .security import decode_token_payload
from . import models

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_photographer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Photographer:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    payload = decode_token_payload(credentials.credentials)
    if not payload or payload.get("role") not in (None, "photographer"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.")
    photographer = db.query(models.Photographer).filter(models.Photographer.id == payload.get("sub")).first()
    if not photographer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Fotógrafo não encontrado.")
    if not photographer.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta conta foi desativada.")
    return photographer


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    payload = decode_token_payload(credentials.credentials)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão de administrador inválida ou expirada.")
    return payload.get("sub")
