import json
import random
import string
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_photographer
from ..storage import save_upload, preview_path_for, preview_url
from ..imaging import make_preview

router = APIRouter(tags=["galleries"])

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gen_code() -> str:
    return "REV-" + "".join(random.choice(CODE_CHARS) for _ in range(5))


def _gallery_out(gallery: models.Gallery) -> schemas.GalleryOut:
    return schemas.GalleryOut(
        id=gallery.id,
        code=gallery.code,
        title=gallery.title,
        client_name=gallery.client_name,
        free_count=gallery.free_count,
        extra_price=gallery.extra_price,
        created_at=gallery.created_at,
        photos=[
            schemas.GalleryPhotoOut(id=p.id, preview_url=preview_url(p.preview_path))
            for p in gallery.photos
        ],
    )


# ---------------------------------------------------------------- fotógrafo
@router.post("/galleries", response_model=schemas.GalleryOut)
def create_gallery(
    payload: schemas.GalleryCreateIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    code = gen_code()
    while db.query(models.Gallery).filter(models.Gallery.code == code).first():
        code = gen_code()

    gallery = models.Gallery(
        code=code,
        photographer_id=photographer.id,
        title=payload.title.strip(),
        client_name=payload.client_name.strip(),
        free_count=payload.free_count,
        extra_price=payload.extra_price,
    )
    db.add(gallery)
    db.commit()
    db.refresh(gallery)
    return _gallery_out(gallery)


@router.get("/galleries", response_model=List[schemas.GalleryOut])
def list_my_galleries(
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    galleries = (
        db.query(models.Gallery)
        .filter(models.Gallery.photographer_id == photographer.id)
        .order_by(models.Gallery.created_at.desc())
        .all()
    )
    return [_gallery_out(g) for g in galleries]


@router.get("/galleries/{gallery_id}", response_model=schemas.GalleryOut)
def get_gallery(
    gallery_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    return _gallery_out(gallery)


@router.post("/galleries/{gallery_id}/photos", response_model=schemas.GalleryOut)
def upload_gallery_photos(
    gallery_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)

    for f in files:
        original_path = save_upload(f, subfolder=f"gallery_{gallery.id}")
        preview_path = preview_path_for(original_path, subfolder=f"gallery_{gallery.id}")
        make_preview(original_path, preview_path)
        photo = models.GalleryPhoto(
            gallery_id=gallery.id,
            original_path=original_path,
            preview_path=preview_path,
        )
        db.add(photo)

    db.commit()
    db.refresh(gallery)
    return _gallery_out(gallery)


@router.delete("/galleries/{gallery_id}")
def delete_gallery(
    gallery_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    db.delete(gallery)
    db.commit()
    return {"ok": True}


@router.get("/galleries/{gallery_id}/selection", response_model=schemas.SelectionOut)
def get_selection(
    gallery_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    sel = gallery.selection
    if not sel:
        return schemas.SelectionOut(selected_photo_ids=[], extra_count=0, extra_cost=0.0, confirmed_at=None)
    return schemas.SelectionOut(
        selected_photo_ids=json.loads(sel.selected_photo_ids),
        extra_count=sel.extra_count,
        extra_cost=sel.extra_cost,
        confirmed_at=sel.confirmed_at,
    )


def _get_owned_gallery(db: Session, gallery_id: str, photographer_id: str) -> models.Gallery:
    gallery = db.query(models.Gallery).filter(models.Gallery.id == gallery_id).first()
    if not gallery or gallery.photographer_id != photographer_id:
        raise HTTPException(status_code=404, detail="Galeria não encontrada.")
    return gallery


# ---------------------------------------------------------------- público (cliente)
@router.get("/public/galleries/{code}", response_model=schemas.GalleryOut)
def public_get_gallery(code: str, db: Session = Depends(get_db)):
    gallery = db.query(models.Gallery).filter(models.Gallery.code == code.upper()).first()
    if not gallery:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return _gallery_out(gallery)


@router.post("/public/galleries/{code}/selection", response_model=schemas.SelectionOut)
def public_submit_selection(code: str, payload: schemas.SelectionIn, db: Session = Depends(get_db)):
    gallery = db.query(models.Gallery).filter(models.Gallery.code == code.upper()).first()
    if not gallery:
        raise HTTPException(status_code=404, detail="Código não encontrado.")

    valid_ids = {p.id for p in gallery.photos}
    selected = [pid for pid in payload.selected_photo_ids if pid in valid_ids]

    extra_count = max(0, len(selected) - gallery.free_count)
    extra_cost = round(extra_count * gallery.extra_price, 2)

    sel = gallery.selection
    if not sel:
        sel = models.Selection(gallery_id=gallery.id)
        db.add(sel)

    sel.selected_photo_ids = json.dumps(selected)
    sel.extra_count = extra_count
    sel.extra_cost = extra_cost
    sel.confirmed_at = datetime.utcnow()
    sel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sel)

    return schemas.SelectionOut(
        selected_photo_ids=selected,
        extra_count=extra_count,
        extra_cost=extra_cost,
        confirmed_at=sel.confirmed_at,
    )
