import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship

from .database import Base


def uid():
    return uuid.uuid4().hex


class Photographer(Base):
    __tablename__ = "photographers"

    id = Column(String, primary_key=True, default=uid)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    galleries = relationship("Gallery", back_populates="photographer", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="photographer", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Galeria com seleção: cliente recebe um código, marca as fotos que quer e
# paga por unidades além do pacote incluso. (Fluxo do protótipo original.)
# ---------------------------------------------------------------------------
class Gallery(Base):
    __tablename__ = "galleries"

    id = Column(String, primary_key=True, default=uid)
    code = Column(String, unique=True, nullable=False, index=True)
    photographer_id = Column(String, ForeignKey("photographers.id"), nullable=False)
    title = Column(String, nullable=False)
    client_name = Column(String, nullable=False)
    free_count = Column(Integer, default=0)
    extra_price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    photographer = relationship("Photographer", back_populates="galleries")
    photos = relationship("GalleryPhoto", back_populates="gallery", cascade="all, delete-orphan")
    selection = relationship("Selection", back_populates="gallery", uselist=False, cascade="all, delete-orphan")


class GalleryPhoto(Base):
    __tablename__ = "gallery_photos"

    id = Column(String, primary_key=True, default=uid)
    gallery_id = Column(String, ForeignKey("galleries.id"), nullable=False)
    original_path = Column(String, nullable=False)   # arquivo em alta resolução, privado
    preview_path = Column(String, nullable=False)     # arquivo em baixa resolução + marca d'água, público
    created_at = Column(DateTime, default=datetime.utcnow)

    gallery = relationship("Gallery", back_populates="photos")


class Selection(Base):
    __tablename__ = "selections"

    id = Column(String, primary_key=True, default=uid)
    gallery_id = Column(String, ForeignKey("galleries.id"), nullable=False, unique=True)
    selected_photo_ids = Column(Text, default="[]")  # JSON: lista de GalleryPhoto.id
    extra_count = Column(Integer, default=0)
    extra_cost = Column(Float, default=0.0)
    confirmed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)

    gallery = relationship("Gallery", back_populates="selection")


# ---------------------------------------------------------------------------
# Evento com busca por reconhecimento facial: o fotógrafo sobe todas as fotos
# de um evento/campeonato e compartilha um link público. Qualquer pessoa entra
# sem código, envia uma selfie e recebe só as fotos em que ela aparece.
# ---------------------------------------------------------------------------
class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=uid)
    slug = Column(String, unique=True, nullable=False, index=True)
    photographer_id = Column(String, ForeignKey("photographers.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    photographer = relationship("Photographer", back_populates="events")
    photos = relationship("EventPhoto", back_populates="event", cascade="all, delete-orphan")


class EventPhoto(Base):
    __tablename__ = "event_photos"

    id = Column(String, primary_key=True, default=uid)
    event_id = Column(String, ForeignKey("events.id"), nullable=False)
    original_path = Column(String, nullable=False)
    preview_path = Column(String, nullable=False)
    face_count = Column(Integer, default=0)
    processed = Column(Boolean, default=False)  # se o reconhecimento facial já rodou
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event", back_populates="photos")
    encodings = relationship("FaceEncoding", back_populates="photo", cascade="all, delete-orphan")


class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(String, primary_key=True, default=uid)
    event_photo_id = Column(String, ForeignKey("event_photos.id"), nullable=False, index=True)
    encoding_json = Column(Text, nullable=False)  # JSON: vetor de 128 floats

    photo = relationship("EventPhoto", back_populates="encodings")


# ---------------------------------------------------------------------------
# Recuperação de senha: token de uso único, com validade curta, enviado por
# e-mail para o fotógrafo redefinir a senha sem precisar falar com suporte.
# ---------------------------------------------------------------------------
class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True, default=uid)
    photographer_id = Column(String, ForeignKey("photographers.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
