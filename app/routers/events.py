import json
import re
import unicodedata
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import get_current_photographer
from ..storage import save_upload, preview_path_for, preview_url
from ..imaging import make_preview
from .. import face_engine

router = APIRouter(tags=["events"])


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "evento"


def gen_slug(title: str) -> str:
    return f"{slugify(title)}-{uuid.uuid4().hex[:5]}"


def _event_out(event: models.Event, with_photos: bool = False):
    base = dict(
        id=event.id,
        slug=event.slug,
        title=event.title,
        description=event.description,
        created_at=event.created_at,
        photo_count=len(event.photos),
    )
    if with_photos:
        base["photos"] = [
            schemas.EventPhotoOut(
                id=p.id,
                preview_url=preview_url(p.preview_path),
                face_count=p.face_count,
                processed=p.processed,
            )
            for p in event.photos
        ]
        return schemas.EventDetailOut(**base)
    return schemas.EventOut(**base)


# ---------------------------------------------------------------- fotógrafo
@router.post("/events", response_model=schemas.EventOut)
def create_event(
    payload: schemas.EventCreateIn,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    slug = gen_slug(payload.title)
    while db.query(models.Event).filter(models.Event.slug == slug).first():
        slug = gen_slug(payload.title)

    event = models.Event(
        slug=slug,
        photographer_id=photographer.id,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_out(event)


@router.get("/events", response_model=List[schemas.EventOut])
def list_my_events(
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    events = (
        db.query(models.Event)
        .filter(models.Event.photographer_id == photographer.id)
        .order_by(models.Event.created_at.desc())
        .all()
    )
    return [_event_out(e) for e in events]


@router.get("/events/{event_id}", response_model=schemas.EventDetailOut)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    event = _get_owned_event(db, event_id, photographer.id)
    return _event_out(event, with_photos=True)


@router.post("/events/{event_id}/photos", response_model=schemas.EventDetailOut)
def upload_event_photos(
    event_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    """
    Salva cada foto, gera a versão pública em baixa resolução com marca
    d'água e roda o reconhecimento facial pra extrair os vetores de cada
    rosto encontrado. O processamento é síncrono (mais simples de rodar em
    qualquer plataforma); em um evento com muitas fotos de uma vez, o upload
    pode demorar alguns segundos por imagem — a barra de progresso no
    frontend deve refletir isso.
    """
    event = _get_owned_event(db, event_id, photographer.id)

    for f in files:
        original_path = save_upload(f, subfolder=f"event_{event.id}")
        preview_path = preview_path_for(original_path, subfolder=f"event_{event.id}")
        make_preview(original_path, preview_path)

        photo = models.EventPhoto(
            event_id=event.id,
            original_path=original_path,
            preview_path=preview_path,
        )
        db.add(photo)
        db.flush()  # garante photo.id antes de gravar os encodings

        try:
            encodings = face_engine.extract_encodings(original_path)
        except Exception:
            encodings = []

        for enc in encodings:
            db.add(models.FaceEncoding(event_photo_id=photo.id, encoding_json=json.dumps(enc)))

        photo.face_count = len(encodings)
        photo.processed = True

    db.commit()
    db.refresh(event)
    return _event_out(event, with_photos=True)


@router.delete("/events/{event_id}")
def delete_event(
    event_id: str,
    db: Session = Depends(get_db),
    photographer: models.Photographer = Depends(get_current_photographer),
):
    event = _get_owned_event(db, event_id, photographer.id)
    db.delete(event)
    db.commit()
    return {"ok": True}


def _get_owned_event(db: Session, event_id: str, photographer_id: str) -> models.Event:
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event or event.photographer_id != photographer_id:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    return event


# ---------------------------------------------------------------- público
@router.get("/public/events/{slug}", response_model=schemas.EventOut)
def public_get_event(slug: str, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.slug == slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    return _event_out(event)


@router.post("/public/events/{slug}/search", response_model=List[schemas.FaceMatchOut])
def public_face_search(slug: str, selfie: UploadFile = File(...), db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.slug == slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")

    tmp_path = save_upload(selfie, subfolder=f"selfies_{event.id}")
    encoding, faces_found = face_engine.extract_single_selfie_encoding(tmp_path)

    if encoding is None:
        raise HTTPException(
            status_code=422,
            detail="Não encontramos um rosto nítido nessa foto. Tente uma selfie com boa iluminação, de frente.",
        )

    photo_ids = [p.id for p in event.photos]
    rows = (
        db.query(models.FaceEncoding)
        .filter(models.FaceEncoding.event_photo_id.in_(photo_ids))
        .all()
    )
    candidates = [(row.event_photo_id, json.loads(row.encoding_json)) for row in rows]

    matches = face_engine.compare(encoding, candidates, tolerance=settings.face_match_tolerance)

    photos_by_id = {p.id: p for p in event.photos}
    results = []
    for photo_id, distance in matches:
        photo = photos_by_id.get(photo_id)
        if not photo:
            continue
        results.append(
            schemas.FaceMatchOut(
                photo_id=photo.id,
                preview_url=preview_url(photo.preview_path),
                confidence=face_engine.distance_to_confidence(distance, settings.face_match_tolerance),
            )
        )
    return results
