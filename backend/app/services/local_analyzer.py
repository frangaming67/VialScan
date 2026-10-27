import base64
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
import onnxruntime as ort

from .analyzer import estimate_severity

MODEL_URL = "https://model.camthink.ai/models/road-damage-object-detection/download?file_id=341"
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "road-damage-object-detection.onnx"
MODEL_CLASSES = {
    0: ("alligator_crack", "fisuración tipo cocodrilo"),
    1: ("other", "grieta en bloque"),
    2: ("other", "grieta genérica"),
    3: ("edge_break", "rotura de borde"),
    4: ("longitudinal_crack", "grieta longitudinal"),
    5: ("pothole", "bache"),
    6: ("transverse_crack", "grieta transversal"),
}
MODEL_SIZE = 640
MIN_CONFIDENCE = 0.20


def _ensure_model() -> None:
    if MODEL_PATH.is_file():
        return
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = MODEL_PATH.with_suffix(".onnx.partial")
    try:
        with httpx.stream("GET", MODEL_URL, follow_redirects=True, timeout=httpx.Timeout(90, connect=15)) as response:
            response.raise_for_status()
            with temporary_path.open("wb") as output:
                for chunk in response.iter_bytes(1024 * 1024):
                    output.write(chunk)
        if temporary_path.stat().st_size < 1_000_000:
            raise RuntimeError("La descarga del modelo local está incompleta.")
        os.replace(temporary_path, MODEL_PATH)
    except Exception as error:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo descargar el modelo local de calles: {error}") from error


@lru_cache(maxsize=1)
def _session() -> ort.InferenceSession:
    _ensure_model()
    return ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])


def analyze_local_image(image_bytes: bytes) -> dict[str, Any]:
    encoded_image = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded_image, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("No se pudo abrir una de las imágenes. Usa JPG, PNG o WEBP.")

    height, width = image.shape[:2]
    scale = min(MODEL_SIZE / width, MODEL_SIZE / height)
    resized_width, resized_height = round(width * scale), round(height * scale)
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((MODEL_SIZE, MODEL_SIZE, 3), 114, dtype=np.uint8)
    pad_x, pad_y = (MODEL_SIZE - resized_width) // 2, (MODEL_SIZE - resized_height) // 2
    canvas[pad_y:pad_y + resized_height, pad_x:pad_x + resized_width] = resized
    tensor = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0

    model = _session()
    output = model.run(None, {model.get_inputs()[0].name: tensor})[0][0]
    detections = []
    for row in output:
        x1, y1, x2, y2, confidence, class_id = [float(value) for value in row]
        if confidence < MIN_CONFIDENCE:
            continue
        defect_type, label = MODEL_CLASSES.get(int(class_id), ("other", "defecto de pavimento"))
        left = max(0.0, min(float(width), (x1 - pad_x) / scale))
        top = max(0.0, min(float(height), (y1 - pad_y) / scale))
        right = max(left, min(float(width), (x2 - pad_x) / scale))
        bottom = max(top, min(float(height), (y2 - pad_y) / scale))
        bbox_approx = [left / width, top / height, (right - left) / width, (bottom - top) / height]
        severity, severity_score = estimate_severity({
            "type": defect_type,
            "confidence": confidence,
            "bbox_approx": bbox_approx,
        })
        detections.append({
            "defect_type": defect_type,
            "label": label,
            "confidence": round(confidence, 4),
            "severity_estimated": severity,
            "severity_score": severity_score,
            "bbox_approx": [round(value, 4) for value in bbox_approx],
            "description": f"Detector local: {label}. Revisar manualmente; no estima profundidad.",
        })

    detections.sort(key=lambda item: item["confidence"], reverse=True)
    detections = detections[:8]
    preview = image
    if max(height, width) > 960:
        preview_scale = 960 / max(height, width)
        preview = cv2.resize(image, (round(width * preview_scale), round(height * preview_scale)))
    success, jpeg = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not success:
        raise ValueError("No se pudo preparar la vista previa de la imagen.")

    max_confidence = max((item["confidence"] for item in detections), default=0.0)
    if max_confidence >= 0.45:
        road_condition = "poor"
        summary = f"El modelo encontró {len(detections)} señal(es) de daño; requiere revisión humana."
    elif detections:
        road_condition = "fair"
        summary = f"El modelo encontró {len(detections)} señal(es) de daño con confianza moderada."
    else:
        road_condition = "good"
        summary = "El detector no encontró daños sobre el umbral; esto no certifica el buen estado de la calle."

    return {
        "road_condition": road_condition,
        "frame_confidence": round(max_confidence or 0.35, 4),
        "summary": summary,
        "detections": detections,
        "evidence_url": f"data:image/jpeg;base64,{base64.b64encode(jpeg.tobytes()).decode('ascii')}",
    }
