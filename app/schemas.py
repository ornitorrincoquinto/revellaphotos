from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str
    username: str
    password: str = Field(min_length=6)
    email: Optional[EmailStr] = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    photographer_name: str


# ---------- galleries (seleção com cobrança de extras) ----------
class GalleryCreateIn(BaseModel):
    title: str
    client_name: str
    free_count: int = Field(ge=0)
    extra_price: float = Field(ge=0)


class GalleryPhotoOut(BaseModel):
    id: str
    preview_url: str

    class Config:
        from_attributes = True


class GalleryOut(BaseModel):
    id: str
    code: str
    title: str
    client_name: str
    free_count: int
    extra_price: float
    created_at: datetime
    photos: List[GalleryPhotoOut] = []

    class Config:
        from_attributes = True


class SelectionIn(BaseModel):
    selected_photo_ids: List[str]


class SelectionOut(BaseModel):
    selected_photo_ids: List[str]
    extra_count: int
    extra_cost: float
    confirmed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------- events (busca facial) ----------
class EventCreateIn(BaseModel):
    title: str
    description: Optional[str] = None


class EventPhotoOut(BaseModel):
    id: str
    preview_url: str
    face_count: int
    processed: bool

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: str
    slug: str
    title: str
    description: Optional[str]
    created_at: datetime
    photo_count: int = 0

    class Config:
        from_attributes = True


class EventDetailOut(EventOut):
    photos: List[EventPhotoOut] = []


class FaceMatchOut(BaseModel):
    photo_id: str
    preview_url: str
    confidence: float  # 0 a 100, quanto maior mais parecido
