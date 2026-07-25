from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut)
def register(payload: schemas.RegisterIn, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    existing = db.query(models.Photographer).filter(models.Photographer.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Esse usuário já existe.")

    photographer = models.Photographer(
        name=payload.name.strip(),
        username=username,
        email=payload.email,
        password_hash=security.hash_password(payload.password),
    )
    db.add(photographer)
    db.commit()
    db.refresh(photographer)

    token = security.create_access_token(subject=photographer.id)
    return schemas.TokenOut(access_token=token, photographer_name=photographer.name)


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    photographer = db.query(models.Photographer).filter(models.Photographer.username == username).first()
    if not photographer or not security.verify_password(payload.password, photographer.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha incorretos.")

    token = security.create_access_token(subject=photographer.id)
    return schemas.TokenOut(access_token=token, photographer_name=photographer.name)
