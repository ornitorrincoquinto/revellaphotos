import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from ..deps import get_current_photographer
from ..email_utils import send_email

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TOKEN_EXPIRE_MINUTES = 30


@router.post("/register", response_model=schemas.TokenOut)
def register(payload: schemas.RegisterIn, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    existing = db.query(models.Photographer).filter(models.Photographer.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Esse usuário já existe.")

    photographer = models.Photographer(
        name=payload.name.strip(),
        username=username,
        email=(payload.email or None),
        phone=(payload.phone.strip() if payload.phone else None),
        password_hash=security.hash_password(payload.password),
    )
    db.add(photographer)
    db.commit()
    db.refresh(photographer)

    token = security.create_access_token(subject=photographer.id, role="photographer")
    return schemas.TokenOut(access_token=token, photographer_name=photographer.name)


@router.post("/login", response_model=schemas.TokenOut)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    photographer = db.query(models.Photographer).filter(models.Photographer.username == username).first()
    if not photographer or not security.verify_password(payload.password, photographer.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha incorretos.")
    if not photographer.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Esta conta foi desativada.")

    token = security.create_access_token(subject=photographer.id, role="photographer")
    return schemas.TokenOut(access_token=token, photographer_name=photographer.name)


# ---------------------------------------------------------------------------
# Recuperação de senha. A resposta é sempre a mesma mensagem genérica, exista
# ou não o usuário/e-mail — evita que alguém use esse endpoint pra descobrir
# quais contas existem no sistema.
# ---------------------------------------------------------------------------
@router.post("/forgot-password", response_model=schemas.MessageOut)
def forgot_password(payload: schemas.ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    generic_message = "Se esse usuário ou e-mail existir, enviamos um link de redefinição de senha."
    identifier = payload.identifier.strip().lower()
    if not identifier:
        return schemas.MessageOut(message=generic_message)

    photographer = (
        db.query(models.Photographer)
        .filter(
            (models.Photographer.username == identifier)
            | (models.Photographer.email == identifier)
        )
        .first()
    )

    if photographer and photographer.email:
        token = secrets.token_urlsafe(32)
        reset = models.PasswordResetToken(
            photographer_id=photographer.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
        )
        db.add(reset)
        db.commit()

        base_url = str(request.base_url).rstrip("/")
        link = f"{base_url}/redefinir-senha?token={token}"
        send_email(
            to_email=photographer.email,
            subject="Redefinição de senha — REVELA",
            body=(
                f"Olá, {photographer.name}!\n\n"
                f"Recebemos um pedido para redefinir a senha da sua conta REVELA.\n"
                f"Clique no link abaixo para criar uma nova senha (válido por {RESET_TOKEN_EXPIRE_MINUTES} minutos):\n\n"
                f"{link}\n\n"
                f"Se você não pediu isso, pode ignorar este e-mail."
            ),
        )

    return schemas.MessageOut(message=generic_message)


@router.post("/reset-password", response_model=schemas.MessageOut)
def reset_password(payload: schemas.ResetPasswordIn, db: Session = Depends(get_db)):
    reset = db.query(models.PasswordResetToken).filter(models.PasswordResetToken.token == payload.token).first()
    if not reset or reset.used or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Peça uma nova redefinição.")

    photographer = db.query(models.Photographer).filter(models.Photographer.id == reset.photographer_id).first()
    if not photographer:
        raise HTTPException(status_code=400, detail="Conta não encontrada.")

    photographer.password_hash = security.hash_password(payload.new_password)
    reset.used = True
    db.commit()

    return schemas.MessageOut(message="Senha redefinida com sucesso. Você já pode entrar com a nova senha.")


# ---------------------------------------------------------------------------
# Perfil do fotógrafo — nome, e-mail, telefone e a chave Pix usada pra gerar
# o QR code de cobrança das fotos extras (ver routers/galleries.py).
# ---------------------------------------------------------------------------
@router.get("/me", response_model=schemas.ProfileOut)
def get_me(photographer: models.Photographer = Depends(get_current_photographer)):
    return photographer


@router.patch("/me", response_model=schemas.ProfileOut)
def update_me(
    payload: schemas.ProfileUpdateIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    if payload.name is not None and payload.name.strip():
        photographer.name = payload.name.strip()
    if payload.email is not None:
        new_email = payload.email or None
        if new_email:
            clash = (
                db.query(models.Photographer)
                .filter(models.Photographer.email == new_email, models.Photographer.id != photographer.id)
                .first()
            )
            if clash:
                raise HTTPException(status_code=400, detail="Esse e-mail já está em uso por outra conta.")
        photographer.email = new_email
    if payload.phone is not None:
        photographer.phone = payload.phone.strip() or None
    if payload.pix_key is not None:
        photographer.pix_key = payload.pix_key.strip() or None
    if payload.pix_city is not None:
        photographer.pix_city = payload.pix_city.strip() or None
    db.commit()
    db.refresh(photographer)
    return photographer


@router.post("/me/change-password", response_model=schemas.MessageOut)
def change_password(
    payload: schemas.ChangePasswordIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    if not security.verify_password(payload.current_password, photographer.password_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    photographer.password_hash = security.hash_password(payload.new_password)
    db.commit()
    return schemas.MessageOut(message="Senha alterada com sucesso.")
