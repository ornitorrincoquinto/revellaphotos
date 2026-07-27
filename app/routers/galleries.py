import io
import json
import os
import random
import zipfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from .. import pix
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
        locked=bool(gallery.lock_pin),
        created_at=gallery.created_at,
        photos=[
            schemas.GalleryPhotoOut(id=p.id, preview_url=preview_url(p.preview_path))
            for p in gallery.photos
        ],
    )


def _gallery_owner_out(gallery: models.Gallery) -> schemas.GalleryOwnerOut:
    return schemas.GalleryOwnerOut(**_gallery_out(gallery).model_dump(), lock_pin=gallery.lock_pin)


def _selection_out(sel: Optional[models.Selection]) -> schemas.SelectionOut:
    if not sel:
        return schemas.SelectionOut()
    return schemas.SelectionOut(
        package_photo_ids=json.loads(sel.package_photo_ids or "[]"),
        package_confirmed_at=sel.package_confirmed_at,
        extra_photo_ids=json.loads(sel.extra_photo_ids or "[]"),
        extra_count=sel.extra_count,
        extra_cost=sel.extra_cost,
        extras_confirmed_at=sel.extras_confirmed_at,
        payment_status=sel.payment_status,
        payment_confirmed_at=sel.payment_confirmed_at,
    )


def _validate_pin(pin: Optional[str]):
    if pin is not None and pin and not (pin.isdigit() and len(pin) == 6):
        raise HTTPException(status_code=400, detail="O PIN precisa ter exatamente 6 dígitos numéricos.")


def _check_gallery_pin(gallery: models.Gallery, pin: Optional[str]):
    if gallery.lock_pin and gallery.lock_pin != (pin or ""):
        raise HTTPException(status_code=401, detail="PIN necessário ou incorreto para abrir esta galeria.")


def _get_public_gallery(db: Session, code: str) -> models.Gallery:
    gallery = db.query(models.Gallery).filter(models.Gallery.code == code.upper()).first()
    if not gallery:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return gallery


def _get_owned_gallery(db: Session, gallery_id: str, photographer_id: str) -> models.Gallery:
    gallery = db.query(models.Gallery).filter(models.Gallery.id == gallery_id).first()
    if not gallery or gallery.photographer_id != photographer_id:
        raise HTTPException(status_code=404, detail="Galeria não encontrada.")
    return gallery


def _get_or_create_selection(db: Session, gallery: models.Gallery) -> models.Selection:
    if not gallery.selection:
        sel = models.Selection(gallery_id=gallery.id)
        db.add(sel)
        db.flush()
        return sel
    return gallery.selection


# =================================================================== fotógrafo
@router.post("/galleries", response_model=schemas.GalleryOwnerOut)
def create_gallery(
    payload: schemas.GalleryCreateIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    _validate_pin(payload.lock_pin)
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
        lock_pin=(payload.lock_pin.strip() if payload.lock_pin else None),
    )
    db.add(gallery)
    db.commit()
    db.refresh(gallery)
    return _gallery_owner_out(gallery)


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


@router.get("/galleries/{gallery_id}", response_model=schemas.GalleryOwnerOut)
def get_gallery(
    gallery_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    return _gallery_owner_out(gallery)


@router.patch("/galleries/{gallery_id}", response_model=schemas.GalleryOwnerOut)
def update_gallery(
    gallery_id: str,
    payload: schemas.GalleryUpdateIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    if payload.title is not None and payload.title.strip():
        gallery.title = payload.title.strip()
    if payload.client_name is not None and payload.client_name.strip():
        gallery.client_name = payload.client_name.strip()
    if payload.free_count is not None:
        gallery.free_count = payload.free_count
    if payload.extra_price is not None:
        gallery.extra_price = payload.extra_price
    if payload.lock_pin is not None:
        if payload.lock_pin == "":
            gallery.lock_pin = None
        else:
            _validate_pin(payload.lock_pin)
            gallery.lock_pin = payload.lock_pin.strip()
    db.commit()
    db.refresh(gallery)
    return _gallery_owner_out(gallery)


@router.post("/galleries/{gallery_id}/photos", response_model=schemas.GalleryOwnerOut)
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
    return _gallery_owner_out(gallery)


@router.delete("/galleries/{gallery_id}/photos/{photo_id}", response_model=schemas.GalleryOwnerOut)
def delete_gallery_photo(
    gallery_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    photo = db.query(models.GalleryPhoto).filter(
        models.GalleryPhoto.id == photo_id, models.GalleryPhoto.gallery_id == gallery.id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")

    for path in (photo.original_path, photo.preview_path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    db.delete(photo)
    db.commit()
    db.refresh(gallery)
    return _gallery_owner_out(gallery)


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
    return _selection_out(gallery.selection)


@router.post("/galleries/{gallery_id}/selection/confirm-payment", response_model=schemas.SelectionOut)
def confirm_payment(
    gallery_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    """O fotógrafo confirma manualmente que recebeu o Pix — não existe
    verificação automática, é uma confirmação de confiança do próprio
    fotógrafo, já que o pagamento cai direto na conta dele."""
    gallery = _get_owned_gallery(db, gallery_id, photographer.id)
    sel = gallery.selection
    if not sel or sel.extra_cost <= 0:
        raise HTTPException(status_code=400, detail="Não há cobrança pendente nesta galeria.")
    sel.payment_status = "pago"
    sel.payment_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(sel)
    return _selection_out(sel)


# =================================================================== público (cliente)
@router.get("/public/galleries/{code}", response_model=schemas.GalleryOut)
def public_get_gallery(code: str, pin: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)
    return _gallery_out(gallery)


@router.get("/public/galleries/{code}/selection", response_model=schemas.SelectionOut)
def public_get_selection(code: str, pin: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)
    return _selection_out(gallery.selection)


@router.post("/public/galleries/{code}/confirm-package", response_model=schemas.SelectionOut)
def public_confirm_package(
    code: str,
    payload: schemas.PackageConfirmIn,
    pin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Confirma a seleção do pacote contratado. Depois disso, essas fotos
    ficam liberadas para download e não podem mais ser trocadas — só dá pra
    escolher fotos extras a partir daqui."""
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)

    valid_ids = {p.id for p in gallery.photos}
    selected = [pid for pid in payload.selected_photo_ids if pid in valid_ids]
    if len(selected) == 0:
        raise HTTPException(status_code=400, detail="Selecione ao menos uma foto do pacote.")
    if len(selected) > gallery.free_count:
        raise HTTPException(
            status_code=400,
            detail=f"O pacote contratado inclui {gallery.free_count} foto(s). Você selecionou {len(selected)}.",
        )

    sel = _get_or_create_selection(db, gallery)
    if sel.package_confirmed_at:
        raise HTTPException(status_code=400, detail="O pacote contratado já foi confirmado e não pode ser alterado.")

    sel.package_photo_ids = json.dumps(selected)
    sel.package_confirmed_at = datetime.utcnow()
    sel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(sel)
    return _selection_out(sel)


@router.post("/public/galleries/{code}/confirm-extras", response_model=schemas.SelectionOut)
def public_confirm_extras(
    code: str,
    payload: schemas.ExtrasConfirmIn,
    pin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Confirma as fotos extras (além do pacote). Só pode ser chamado depois
    do pacote confirmado, e não pode reaproveitar fotos já usadas no pacote."""
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)

    sel = gallery.selection
    if not sel or not sel.package_confirmed_at:
        raise HTTPException(status_code=400, detail="Confirme primeiro a seleção do pacote contratado.")
    if sel.payment_status == "pago":
        raise HTTPException(status_code=400, detail="O pagamento das extras já foi confirmado pelo fotógrafo.")

    package_ids = set(json.loads(sel.package_photo_ids or "[]"))
    valid_ids = {p.id for p in gallery.photos} - package_ids
    selected_extras = [pid for pid in payload.selected_extra_photo_ids if pid in valid_ids]

    extra_count = len(selected_extras)
    extra_cost = round(extra_count * gallery.extra_price, 2)

    sel.extra_photo_ids = json.dumps(selected_extras)
    sel.extra_count = extra_count
    sel.extra_cost = extra_cost
    sel.extras_confirmed_at = datetime.utcnow()
    sel.updated_at = datetime.utcnow()
    sel.payment_status = "aguardando_pagamento" if extra_cost > 0 else "sem_cobranca"
    db.commit()
    db.refresh(sel)
    return _selection_out(sel)


@router.get("/public/galleries/{code}/pix-qrcode", response_model=schemas.PixQrOut)
def public_pix_qrcode(code: str, pin: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)

    sel = gallery.selection
    if not sel or sel.extra_cost <= 0:
        raise HTTPException(status_code=400, detail="Não há valor adicional a cobrar nesta galeria.")

    photographer = gallery.photographer
    if not photographer.pix_key:
        raise HTTPException(
            status_code=400,
            detail="O fotógrafo ainda não configurou uma chave Pix. Combine o pagamento diretamente com ele.",
        )

    try:
        payload = pix.build_pix_payload(
            pix_key=photographer.pix_key,
            merchant_name=photographer.name,
            merchant_city=photographer.pix_city,
            amount=sel.extra_cost,
            txid=gallery.code,
            description=f"Fotos extras {gallery.title}"[:40],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schemas.PixQrOut(
        payload=payload,
        qr_data_uri=pix.payload_to_qr_data_uri(payload),
        amount=sel.extra_cost,
        merchant_name=photographer.name,
    )


@router.get("/public/galleries/{code}/photos/{photo_id}/download")
def public_download_photo(
    code: str,
    photo_id: str,
    pin: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Libera o arquivo original em alta resolução — só para fotos do pacote
    já confirmado, ou fotos extras já pagas (confirmadas pelo fotógrafo)."""
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)

    photo = db.query(models.GalleryPhoto).filter(
        models.GalleryPhoto.id == photo_id, models.GalleryPhoto.gallery_id == gallery.id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto não encontrada.")

    sel = gallery.selection
    package_ids = set(json.loads(sel.package_photo_ids or "[]")) if sel else set()
    extra_ids = set(json.loads(sel.extra_photo_ids or "[]")) if sel else set()

    released = photo_id in package_ids or (photo_id in extra_ids and sel and sel.payment_status == "pago")
    if not released:
        raise HTTPException(status_code=403, detail="Esta foto ainda não está liberada para download.")

    if not os.path.exists(photo.original_path):
        raise HTTPException(status_code=404, detail="Arquivo original não encontrado no servidor.")

    ext = os.path.splitext(photo.original_path)[1] or ".jpg"
    return FileResponse(
        photo.original_path,
        filename=f"{gallery.code}-{photo_id[:8]}{ext}",
        media_type="application/octet-stream",
    )


def _released_photos(gallery: models.Gallery) -> List[models.GalleryPhoto]:
    sel = gallery.selection
    if not sel:
        return []
    package_ids = set(json.loads(sel.package_photo_ids or "[]"))
    extra_ids = set(json.loads(sel.extra_photo_ids or "[]")) if sel.payment_status == "pago" else set()
    released_ids = package_ids | extra_ids
    return [p for p in gallery.photos if p.id in released_ids]


@router.get("/public/galleries/{code}/download-all")
def public_download_all(code: str, pin: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    """Baixa todas as fotos já liberadas (pacote confirmado + extras pagas) num único .zip."""
    gallery = _get_public_gallery(db, code)
    _check_gallery_pin(gallery, pin)

    photos = _released_photos(gallery)
    if not photos:
        raise HTTPException(status_code=400, detail="Nenhuma foto liberada para download ainda.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for i, photo in enumerate(photos, start=1):
            if not os.path.exists(photo.original_path):
                continue
            ext = os.path.splitext(photo.original_path)[1] or ".jpg"
            zf.write(photo.original_path, arcname=f"{gallery.code}-{i:03d}{ext}")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{gallery.code}-fotos.zip"'},
    )
