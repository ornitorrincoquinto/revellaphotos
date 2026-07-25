"""
Motor de reconhecimento facial, 100% open-source e self-hosted (biblioteca
`face_recognition`, baseada em dlib — sem custo por foto processada, sem
serviço externo). Roda inteiramente no seu servidor.

Observação de escala: aqui a comparação é feita "na força bruta" (carrega
todos os vetores do evento e compara um a um). Para eventos com poucas
centenas/milhares de fotos isso é tranquilo. Se um dia um evento tiver
dezenas de milhares de fotos, vale migrar a busca para um índice vetorial
(ex: extensão pgvector no Postgres) — a estrutura de dados aqui já foi
pensada pra permitir essa migração sem muito retrabalho.
"""
from typing import List, Tuple

import face_recognition
import numpy as np


def extract_encodings(image_path: str) -> List[List[float]]:
    """Detecta todos os rostos numa foto e devolve um vetor de 128 posições por rosto."""
    image = face_recognition.load_image_file(image_path)
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
    image = face_recognition.load_image_file(image_path)
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
