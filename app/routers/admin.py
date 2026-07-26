import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..config import settings
from ..database import get_db
from ..deps import get_current_admin
from .galleries import _gallery_out, _selection_out

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=schemas.AdminTokenOut)
def admin_login(payload: schemas.AdminLoginIn):
    if not settings.admin_username or not settings.admin_password:
        raise HTTPException(
            status_code=503,
            detail="Painel master não configurado. Defina ADMIN_USERNAME e ADMIN_PASSWORD no servidor.",
        )
    user_ok = secrets.compare_digest(payload.username.strip(), settings.admin_username)
    pass_ok = secrets.compare_digest(payload.password, settings.admin_password)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="Usuário ou senha master incorretos.")

    token = security.create_access_token(subject="admin", role="admin")
    return schemas.AdminTokenOut(access_token=token)


@router.get("/photographers", response_model=list[schemas.PhotographerAdminOut])
def list_photographers(
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    photographers = db.query(models.Photographer).order_by(models.Photographer.created_at.desc()).all()
    out = []
    for p in photographers:
        item = schemas.PhotographerAdminOut.model_validate(p)
        item.gallery_count = len(p.galleries)
        item.event_count = len(p.events)
        out.append(item)
    return out


@router.get("/photographers/{photographer_id}", response_model=schemas.PhotographerAdminDetailOut)
def get_photographer(
    photographer_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    p = db.query(models.Photographer).filter(models.Photographer.id == photographer_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Fotógrafo não encontrado.")

    galleries_out = []
    for g in p.galleries:
        item = schemas.AdminGalleryOut(**_gallery_out(g).model_dump())
        item.selection = _selection_out(g.selection)
        galleries_out.append(item)

    return schemas.PhotographerAdminDetailOut(
        id=p.id, name=p.name, username=p.username, email=p.email, phone=p.phone,
        is_active=p.is_active, created_at=p.created_at,
        gallery_count=len(p.galleries), event_count=len(p.events),
        pix_key=p.pix_key, pix_city=p.pix_city,
        galleries=galleries_out,
        events=[schemas.EventOut(id=e.id, slug=e.slug, title=e.title, description=e.description,
                                  created_at=e.created_at, photo_count=len(e.photos)) for e in p.events],
    )


@router.patch("/photographers/{photographer_id}", response_model=schemas.PhotographerAdminOut)
def update_photographer(
    photographer_id: str,
    payload: schemas.PhotographerAdminUpdateIn,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    p = db.query(models.Photographer).filter(models.Photographer.id == photographer_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Fotógrafo não encontrado.")

    if payload.name is not None and payload.name.strip():
        p.name = payload.name.strip()
    if payload.email is not None:
        new_email = payload.email.strip() or None
        if new_email:
            clash = db.query(models.Photographer).filter(
                models.Photographer.email == new_email, models.Photographer.id != p.id
            ).first()
            if clash:
                raise HTTPException(status_code=400, detail="Esse e-mail já está em uso por outra conta.")
        p.email = new_email
    if payload.phone is not None:
        p.phone = payload.phone.strip() or None
    if payload.pix_key is not None:
        p.pix_key = payload.pix_key.strip() or None
    if payload.pix_city is not None:
        p.pix_city = payload.pix_city.strip() or None
    if payload.is_active is not None:
        p.is_active = payload.is_active
    if payload.new_password:
        p.password_hash = security.hash_password(payload.new_password)

    db.commit()
    db.refresh(p)
    item = schemas.PhotographerAdminOut.model_validate(p)
    item.gallery_count = len(p.galleries)
    item.event_count = len(p.events)
    return item


@router.delete("/photographers/{photographer_id}")
def delete_photographer(
    photographer_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(get_current_admin),
):
    p = db.query(models.Photographer).filter(models.Photographer.id == photographer_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Fotógrafo não encontrado.")
    db.delete(p)
    db.commit()
    return {"ok": True}
