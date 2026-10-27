import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import settings


PROMPT_VERSION = "road-condition-v2"
GUIDE_PATH = Path(__file__).resolve().parents[1] / "data" / "road_condition_guide.json"
ROAD_GUIDE = json.loads(GUIDE_PATH.read_text(encoding="utf-8"))
DEFECT_TYPES = [item["id"] for item in ROAD_GUIDE["defects"]]
CONDITION_LEVELS = [item["id"] for item in ROAD_GUIDE["condition_levels"]]

_TYPE_REFERENCE = "\n".join(
    f"- {item['id']}: {item['definition']} Visual cues: {item['visual_cues']} Avoid confusing with: {item['avoid_confusing_with']}"
    for item in ROAD_GUIDE["defects"]
)
_REVIEW_RULES = "\n".join(f"- {item}" for item in ROAD_GUIDE["review_rules"])

PROMPT = f"""Assess the visible drivable road surface in this frame from a moving vehicle.
Use the supplied road-condition reference catalog. Identify up to 8 distinct, clearly visible pavement defects.
For each defect, return its type, a short evidence-based description, confidence from 0 to 1, a rough visual severity estimate, and bbox_approx as [x, y, width, height] normalized from 0 to 1 or [] if unavailable.

Condition definitions:
- good: visible pavement appears continuous with no clearly visible active defect in this frame.
- fair: limited/localized wear, small cracks, repairs, or low-severity defects; the pavement is mostly continuous.
- poor: clearly visible potholes, broad deformation, connected alligator cracking, material loss, or multiple notable defects.
- not_assessable: the drivable road surface is not visible clearly enough to judge.

Defect reference:
{_TYPE_REFERENCE}

Review rules:
{_REVIEW_RULES}

Return an empty defects array when no defect is visibly supported. A repair patch is not automatically an active defect. A dark region alone is not enough to call a pothole. Do not estimate depth, real-world dimensions, age, or exact location from a monocular image. Keep the response concise and factual."""

DEFECT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": [*DEFECT_TYPES]},
        "description": {"type": "string"},
        "confidence": {"type": "number"},
        "severity_estimate": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
        "bbox_approx": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["type", "description", "confidence", "severity_estimate", "bbox_approx"],
    "additionalProperties": False,
}

SCHEMA = {
    "type": "object",
    "properties": {
        "road_condition": {"type": "string", "enum": [*CONDITION_LEVELS]},
        "frame_confidence": {"type": "number"},
        "summary": {"type": "string"},
        "defects": {"type": "array", "items": DEFECT_SCHEMA},
    },
    "required": ["road_condition", "frame_confidence", "summary", "defects"],
    "additionalProperties": False,
}


def analyze_image(image_path: Path) -> tuple[dict[str, Any], str]:
    if not settings.analysis_ready:
        raise RuntimeError("Configura OPENAI_API_KEY y OPENAI_MODEL para analizar imágenes reales.")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    response = OpenAI(api_key=settings.openai_api_key).responses.create(
        model=settings.openai_model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{encoded}", "detail": "high"},
            ],
        }],
        text={"format": {"type": "json_schema", "name": "road_condition_frame", "strict": True, "schema": SCHEMA}},
    )
    parsed = json.loads(response.output_text)
    frame_confidence = float(parsed.get("frame_confidence", 0))
    parsed["frame_confidence"] = max(0.0, min(1.0, frame_confidence))
    for item in parsed.get("defects", []):
        item["confidence"] = max(0.0, min(1.0, float(item.get("confidence", 0))))
        if item.get("type") not in DEFECT_TYPES:
            item["type"] = "other"
    if parsed.get("road_condition") not in CONDITION_LEVELS:
        parsed["road_condition"] = "not_assessable"
    return parsed, response.output_text


def estimate_severity(result: dict[str, Any]) -> tuple[str, float]:
    """Versioned visual heuristic; apparent image area is not a physical measurement."""
    confidence = max(0.0, min(1.0, float(result.get("confidence", 0))))
    bbox = result.get("bbox_approx") or []
    area = 0.0
    if len(bbox) >= 4:
        width = max(0.0, min(1.0, float(bbox[2])))
        height = max(0.0, min(1.0, float(bbox[3])))
        area = min(1.0, width * height)
    class_weight = {
        "pothole": 0.82,
        "alligator_crack": 0.78,
        "deformation": 0.75,
        "rutting": 0.68,
        "edge_break": 0.66,
        "longitudinal_crack": 0.56,
        "transverse_crack": 0.56,
        "raveling": 0.52,
        "patch": 0.35,
        "other": 0.50,
    }.get(result.get("type"), 0.35)
    apparent_area = min(1.0, area * 8)
    score = round(0.45 * class_weight + 0.30 * apparent_area + 0.25 * confidence, 3)
    if confidence < 0.35:
        return "unknown", score
    if score >= 0.68:
        return "high", score
    if score >= 0.43:
        return "medium", score
    return "low", score
