"""
Geração das imagens de pré-visualização: toda foto que qualquer cliente
enxerga (seja na galeria com seleção, seja num evento com busca facial) passa
por aqui primeiro. O arquivo original em alta resolução NUNCA é exposto
publicamente — fica só em disco, acessível ao fotógrafo autenticado.
"""
import os
from PIL import Image, ImageDraw, ImageFont

from .config import settings


def _load_font(size: int):
    # Tenta usar uma fonte comum do sistema; se não achar, cai para a padrão
    # do Pillow (sem TrueType, mas nunca quebra o processamento).
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _apply_watermark(img: Image.Image, text: str) -> Image.Image:
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(18, img.width // 22)
    font = _load_font(font_size)

    text_w = draw.textlength(text, font=font)
    text_h = font_size

    # Marca d'água repetida na diagonal, cobrindo a imagem inteira, para
    # dificultar recorte/uso indevido da prova em baixa resolução.
    step_x = int(text_w) + 90
    step_y = int(text_h) + 70
    tile = Image.new("RGBA", (step_x, step_y), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    tile_draw.text((0, step_y // 2 - text_h // 2), text, font=font, fill=(255, 255, 255, 90))
    tile = tile.rotate(-30, expand=True)

    for y in range(-tile.height, img.height + tile.height, tile.height):
        for x in range(-tile.width, img.width + tile.width, tile.width):
            overlay.alpha_composite(tile, (x, y))

    watermarked = Image.alpha_composite(img, overlay)
    return watermarked.convert("RGB")


def make_preview(source_path: str, dest_path: str) -> None:
    """Redimensiona para baixa resolução e aplica marca d'água. Salva em dest_path."""
    with Image.open(source_path) as img:
        img = img.convert("RGB")
        max_dim = settings.preview_max_dimension
        w, h = img.size
        if max(w, h) > max_dim:
            if w >= h:
                new_w, new_h = max_dim, round(h * max_dim / w)
            else:
                new_h, new_w = max_dim, round(w * max_dim / h)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        watermarked = _apply_watermark(img, settings.watermark_text)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        watermarked.save(dest_path, "JPEG", quality=settings.preview_jpeg_quality, optimize=True)
