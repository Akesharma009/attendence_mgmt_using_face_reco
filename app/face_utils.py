"""
Face recognition engine.

Uses `face_recognition` (dlib ResNet embeddings, 128-d vectors) for encoding
and matching. Embeddings are cached in memory (refreshed on registration /
deletion) so that live attendance recognition does not hit the DB on every
frame.

CPU fallback: FACE_DETECTION_MODEL="hog" (default, works everywhere).
GPU acceleration: set FACE_DETECTION_MODEL="cnn" (requires dlib compiled
with CUDA) for faster / more accurate detection on a machine with a GPU.
"""
import base64
import io
import os
import uuid
from datetime import datetime

import numpy as np
import face_recognition
from PIL import Image

from app.models import db, Student, FaceEmbedding, UnknownFaceLog

# In-memory cache: list of (student_id, vector) tuples, rebuilt on demand.
_ENCODING_CACHE = {"loaded": False, "data": []}


def _decode_base64_image(data_url):
    """Convert a `data:image/jpeg;base64,...` string from the browser into an RGB numpy array."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(data_url)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.array(image), image


def extract_face_encoding(rgb_image, detection_model="hog"):
    """Return (encoding, face_location) for the largest face found, or (None, None)."""
    locations = face_recognition.face_locations(rgb_image, model=detection_model)
    if not locations:
        return None, None
    # Pick the largest detected face (closest to camera)
    locations.sort(key=lambda box: (box[2] - box[0]) * (box[1] - box[3]), reverse=True)
    encodings = face_recognition.face_encodings(rgb_image, known_face_locations=[locations[0]])
    if not encodings:
        return None, None
    return encodings[0], locations[0]


def register_face_images(student, image_data_urls, upload_dir, detection_model="hog"):
    """
    Given a list of base64 data-URL frames captured from the webcam,
    detect + encode a face in each, save the image, and store the embedding.
    Returns (num_saved, errors[]).
    """
    saved = 0
    errors = []
    os.makedirs(upload_dir, exist_ok=True)

    for idx, data_url in enumerate(image_data_urls):
        try:
            rgb_image, pil_image = _decode_base64_image(data_url)
        except Exception as exc:
            errors.append(f"Frame {idx + 1}: could not decode image ({exc})")
            continue

        encoding, location = extract_face_encoding(rgb_image, detection_model)
        if encoding is None:
            errors.append(f"Frame {idx + 1}: no face detected")
            continue

        filename = f"{student.student_code}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(upload_dir, filename)
        pil_image.save(filepath, "JPEG", quality=90)

        rel_path = os.path.relpath(filepath, start=os.path.join(upload_dir, ".."))
        fe = FaceEmbedding(student_id=student.id, image_path=rel_path)
        fe.set_vector(encoding)
        db.session.add(fe)

        if saved == 0:
            student.photo_path = rel_path

        saved += 1

    if saved > 0:
        student.is_face_registered = True
        db.session.commit()
        invalidate_cache()
    else:
        db.session.rollback()

    return saved, errors


def invalidate_cache():
    _ENCODING_CACHE["loaded"] = False
    _ENCODING_CACHE["data"] = []


def _ensure_cache_loaded():
    if _ENCODING_CACHE["loaded"]:
        return
    data = []
    for fe in FaceEmbedding.query.all():
        try:
            data.append((fe.student_id, fe.get_vector()))
        except Exception:
            continue
    _ENCODING_CACHE["data"] = data
    _ENCODING_CACHE["loaded"] = True


def recognize_from_data_url(data_url, tolerance=0.45, detection_model="hog", save_unknown_dir=None, class_id=None):
    """
    Recognize faces in a single webcam frame (base64 data URL).
    Returns a list of dicts: {student_id, distance, confidence, box, matched}
    Unmatched faces are optionally logged.
    """
    _ensure_cache_loaded()
    rgb_image, pil_image = _decode_base64_image(data_url)

    locations = face_recognition.face_locations(rgb_image, model=detection_model)
    if not locations:
        return []

    encodings = face_recognition.face_encodings(rgb_image, known_face_locations=locations)
    results = []

    known_vectors = np.array([v for _, v in _ENCODING_CACHE["data"]]) if _ENCODING_CACHE["data"] else None
    known_ids = [sid for sid, _ in _ENCODING_CACHE["data"]]

    for encoding, box in zip(encodings, locations):
        result = {"box": box, "matched": False, "student_id": None, "distance": None, "confidence": 0.0}

        if known_vectors is not None and len(known_vectors) > 0:
            distances = np.linalg.norm(known_vectors - encoding, axis=1)
            best_idx = int(np.argmin(distances))
            best_distance = float(distances[best_idx])

            if best_distance <= tolerance:
                result["matched"] = True
                result["student_id"] = known_ids[best_idx]
                result["distance"] = best_distance
                result["confidence"] = round(max(0.0, (1 - best_distance / 0.6)) * 100, 1)

        if not result["matched"] and save_unknown_dir:
            os.makedirs(save_unknown_dir, exist_ok=True)
            fname = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
            fpath = os.path.join(save_unknown_dir, fname)
            pil_image.save(fpath, "JPEG", quality=85)
            rel_path = os.path.relpath(fpath, start=os.path.join(save_unknown_dir, ".."))
            db.session.add(UnknownFaceLog(class_id=class_id, image_path=rel_path))
            db.session.commit()

        results.append(result)

    return results
