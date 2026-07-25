from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .security import decode_access_token
from . import models

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_photographer(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Photographer:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    photographer_id = decode_access_token(credentials.credentials)
    if not photographer_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.")
    photographer = db.query(models.Photographer).filter(models.Photographer.id == photographer_id).first()
    if not photographer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Fotógrafo não encontrado.")
    return photographer
