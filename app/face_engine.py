"""
Motor de reconhecimento facial, 100% open-source e self-hosted (biblioteca
`face_recognition`, baseada em dlib — sem custo por foto processada, sem
serviço externo). Roda inteiramente no seu servidor.

IMPORTANTE sobre memória: fotos de celular costumam vir em resolução muito
alta (4000x3000px ou mais). Rodar a detecção facial direto na imagem
original consome memória pesada e pode derrubar o processo em servidores
com RAM limitada (o sintoma é um erro 502 com o deploy reiniciando sozinho
em loop, sem nenhum traceback de erro nos logs — é o sistema operacional
matando o processo por falta de memória, não uma exceção do Python).
Por isso a imagem é redimensionada ANTES de qualquer detecção — a foto
original em alta resolução salva em disco não é alterada, só a cópia usada
para calcular os rostos.

Observação de escala: aqui a comparação é feita "na força bruta" (carrega
todos os vetores do evento e compara um a um). Para eventos com poucas
centenas/milhares de fotos isso é tranquilo. Se um dia um evento tiver
dezenas de milhares de fotos, vale migrar a busca para um índice vetorial
(ex: extensão pgvector no Postgres) — a estrutura de dados aqui já foi
pensada pra permitir essa migração sem muito retrabalho.
"""
import os
from typing import List, Tuple

import face_recognition
import numpy as np
from PIL import Image

# Lado maior, em pixels, usado só para a detecção facial (não afeta a foto
# original nem a pré-visualização). Pode ajustar via variável de ambiente
# se precisar de mais precisão (sobe o uso de memória) ou mais economia.
FACE_DETECT_MAX_DIMENSION = int(os.getenv("FACE_DETECT_MAX_DIMENSION", "1280"))


def _load_resized_rgb_array(image_path: str, max_dim: int = FACE_DETECT_MAX_DIMENSION) -> np.ndarray:
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            if w >= h:
                new_w, new_h = max_dim, max(1, round(h * max_dim / w))
            else:
                new_h, new_w = max_dim, max(1, round(w * max_dim / h))
            img = img.resize((new_w, new_h), Image.LANCZOS)
        return np.array(img)


def extract_encodings(image_path: str) -> List[List[float]]:
    """Detecta todos os rostos numa foto e devolve um vetor de 128 posições por rosto."""
    image = _load_resized_rgb_array(image_path)
    # model="hog" é bem mais rápido em CPU do que "cnn" (que exige GPU pra ser viável).
    locations = face_recognition.face_locations(image, model="hog")
    if not locations:
        return []
    encodings = face_recognition.face_encodings(image, known_face_locations=locations)
    return [enc.tolist() for enc in encodings]


def extract_single_selfie_encoding(image_path: str) -> Tuple[List[float], int]:
    """
    Extrai o encoding do maior rosto encontrado numa selfie (assume que é a
    pessoa que está procurando as próprias fotos). Devolve (encoding, total_de_rostos_encontrados).
    """
    image = _load_resized_rgb_array(image_path)
    locations = face_recognition.face_locations(image, model="hog")
    if not locations:
        return None, 0
    # escolhe o maior rosto (maior área do bounding box) — ajuda quando a
    # selfie tem outras pessoas ao fundo.
    def area(loc):
        top, right, bottom, left = loc
        return (bottom - top) * (right - left)
    biggest = max(locations, key=area)
    encoding = face_recognition.face_encodings(image, known_face_locations=[biggest])[0]
    return encoding.tolist(), len(locations)


def compare(selfie_encoding: List[float], candidates: List[Tuple[str, List[float]]], tolerance: float):
    """
    candidates: lista de (photo_id, encoding_json_list)
    Devolve lista de (photo_id, distancia) para os que baterem dentro da tolerância,
    ordenada da mais parecida pra menos parecida (menor distância primeiro).
    """
    if not candidates:
        return []
    selfie_vec = np.array(selfie_encoding)
    known_vecs = np.array([c[1] for c in candidates])
    distances = np.linalg.norm(known_vecs - selfie_vec, axis=1)

    matches = []
    for (photo_id, _), distance in zip(candidates, distances):
        if distance <= tolerance:
            matches.append((photo_id, float(distance)))

    # se uma mesma foto tiver mais de um rosto batendo (não deveria, mas por
    # segurança), fica só a menor distância por foto.
    best_per_photo = {}
    for photo_id, distance in matches:
        if photo_id not in best_per_photo or distance < best_per_photo[photo_id]:
            best_per_photo[photo_id] = distance

    ordered = sorted(best_per_photo.items(), key=lambda x: x[1])
    return ordered


def distance_to_confidence(distance: float, tolerance: float) -> float:
    """Converte a distância numa % de confiança só pra exibição amigável na UI."""
    confidence = max(0.0, (1 - (distance / (tolerance * 1.6)))) * 100
    return round(min(confidence, 99.0), 1)
