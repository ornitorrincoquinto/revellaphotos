"""
Gera o "Pix Copia e Cola" (o payload padrão EMV usado por QR codes Pix) e a
imagem do QR code correspondente — tudo local, sem chamar nenhuma API de
gateway de pagamento. A cobrança cai direto na chave Pix do fotógrafo; este
servidor nunca vê nem retém o dinheiro, só monta o código.

Referência do formato: manual de Pix do Banco Central (BR Code / EMV QRCPS).
"""
import base64
import io
import re
import unicodedata

import qrcode


def _sanitize(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9 ]", "", text).strip().upper()
    return text[:max_len]


def _tlv(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def _crc16_ccitt(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return format(crc, "04X")


def build_pix_payload(pix_key: str, merchant_name: str, merchant_city: str,
                       amount: float, txid: str = "***", description: str = None) -> str:
    if not pix_key or not pix_key.strip():
        raise ValueError("Chave Pix não configurada.")

    merchant_name = _sanitize(merchant_name, 25) or "REVELA"
    merchant_city = _sanitize(merchant_city, 15) or "BRASIL"
    clean_txid = re.sub(r"[^A-Za-z0-9]", "", txid or "")[:25] or "***"

    mai_value = _tlv("00", "br.gov.bcb.pix") + _tlv("01", pix_key.strip())
    if description:
        mai_value += _tlv("02", _sanitize(description, 40))

    payload = (
        _tlv("00", "01")
        + _tlv("26", mai_value)
        + _tlv("52", "0000")
        + _tlv("53", "986")
    )
    if amount and amount > 0:
        payload += _tlv("54", f"{amount:.2f}")
    payload += (
        _tlv("58", "BR")
        + _tlv("59", merchant_name)
        + _tlv("60", merchant_city)
        + _tlv("62", _tlv("05", clean_txid))
        + "6304"
    )
    return payload + _crc16_ccitt(payload)


def payload_to_qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
