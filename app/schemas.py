from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# ---------- auth ----------
class RegisterIn(BaseModel):
    name: str
    username: str
    password: str = Field(min_length=6)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    photographer_name: str


class ForgotPasswordIn(BaseModel):
    identifier: str  # usuário ou e-mail


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class MessageOut(BaseModel):
    message: str


class ProfileOut(BaseModel):
    name: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    pix_key: Optional[str] = None
    pix_city: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileUpdateIn(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    pix_key: Optional[str] = None
    pix_city: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


# ---------- galleries (seleção com pacote travado + extras pagos) ----------
class GalleryCreateIn(BaseModel):
    title: str
    client_name: str
    free_count: int = Field(ge=0)
    extra_price: float = Field(ge=0)
    lock_pin: Optional[str] = None  # 6 dígitos, opcional


class GalleryUpdateIn(BaseModel):
    title: Optional[str] = None
    client_name: Optional[str] = None
    free_count: Optional[int] = Field(default=None, ge=0)
    extra_price: Optional[float] = Field(default=None, ge=0)
    lock_pin: Optional[str] = None  # enviar string vazia "" remove o PIN


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
    locked: bool = False
    created_at: datetime
    photos: List[GalleryPhotoOut] = []

    class Config:
        from_attributes = True


class GalleryOwnerOut(GalleryOut):
    lock_pin: Optional[str] = None


class PackageConfirmIn(BaseModel):
    selected_photo_ids: List[str]


class ExtrasConfirmIn(BaseModel):
    selected_extra_photo_ids: List[str]


class SelectionOut(BaseModel):
    package_photo_ids: List[str] = []
    package_confirmed_at: Optional[datetime] = None
    extra_photo_ids: List[str] = []
    extra_count: int = 0
    extra_cost: float = 0.0
    extras_confirmed_at: Optional[datetime] = None
    payment_status: str = "sem_cobranca"
    payment_confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PixQrOut(BaseModel):
    payload: str
    qr_data_uri: str
    amount: float
    merchant_name: str


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


# ---------- painel master (admin) ----------
class AdminLoginIn(BaseModel):
    username: str
    password: str


class AdminTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PhotographerAdminOut(BaseModel):
    id: str
    name: str
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    gallery_count: int = 0
    event_count: int = 0

    class Config:
        from_attributes = True


class AdminGalleryOut(GalleryOut):
    selection: Optional[SelectionOut] = None


class PhotographerAdminDetailOut(PhotographerAdminOut):
    pix_key: Optional[str] = None
    pix_city: Optional[str] = None
    galleries: List[AdminGalleryOut] = []
    events: List[EventOut] = []


class PhotographerAdminUpdateIn(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pix_key: Optional[str] = None
    pix_city: Optional[str] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=6)
