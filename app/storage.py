import os
import shutil
import uuid

from fastapi import UploadFile

from .config import settings

ORIGINALS_DIR = os.path.join(settings.media_root, "originals")
PREVIEWS_DIR = os.path.join(settings.media_root, "previews")


def ensure_dirs():
    os.makedirs(ORIGINALS_DIR, exist_ok=True)
    os.makedirs(PREVIEWS_DIR, exist_ok=True)


def save_upload(file: UploadFile, subfolder: str) -> str:
    """Salva o arquivo enviado em media/originals/<subfolder>/<id>.jpg e devolve o caminho."""
    ensure_dirs()
    ext = os.path.splitext(file.filename or "")[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    folder = os.path.join(ORIGINALS_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = os.path.join(folder, filename)
    with open(dest, "wb") as out:
        shutil.copyfileobj(file.file, out)
    return dest


def preview_path_for(original_path: str, subfolder: str) -> str:
    ensure_dirs()
    folder = os.path.join(PREVIEWS_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    base = os.path.splitext(os.path.basename(original_path))[0]
    return os.path.join(folder, f"{base}.jpg")


def preview_url(preview_path: str) -> str:
    # Servido publicamente via StaticFiles montado em /media (ver main.py).
    rel = os.path.relpath(preview_path, settings.media_root)
    return f"/media/{rel.replace(os.sep, '/')}"
