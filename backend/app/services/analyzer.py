import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from ..config import settings


PROMPT_VERSION = "road-condition-v1"
PROMPT = """Inspect this road-surface image from a moving vehicle. Report only defects visibly supported by the pixels.
Allowed defect types: pothole, crack, patch, deformation, other, none.
If no road defect is visible, set has_defect=false and type=none.
Do not infer depth, physical dimensions, or exact location. Confidence is your visual confidence from 0 to 1.
Return bbox_approx as [x, y, width, height] normalized from 0 to 1 for the defect region, or [] when unavailable.
Describe only visible evidence. Severity is a rough visual estimate, not a measurement."""

SCHEMA = {
    "type": "object",
    "properties": {
        "has_defect": {"type": "boolean"},
        "type": {"type": "string", "enum": ["pothole", "crack", "patch", "deformation", "other", "none"]},
        "description": {"type": "string"},
        "confidence": {"type": "number"},
        "severity_estimate": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
        "bbox_approx": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["has_defect", "type", "description", "confidence", "severity_estimate", "bbox_approx"],
    "additionalProperties": False,
}


def analyze_image(image_path: Path) -> tuple[dict[str, Any], str]:
    if not settings.analysis_ready:
        raise RuntimeError("Configura OPENAI_API_KEY y OPENAI_MODEL para analizar videos reales.")
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
        text={"format": {"type": "json_schema", "name": "road_condition_observation", "strict": True, "schema": SCHEMA}},
    )
    parsed = json.loads(response.output_text)
    confidence = float(parsed.get("confidence", 0))
    parsed["confidence"] = max(0.0, min(1.0, confidence))
    return parsed, response.output_text


def estimate_severity(result: dict[str, Any]) -> tuple[str, float]:
    """Versioned heuristic; apparent image area is not a physical size measurement."""
    confidence = max(0.0, min(1.0, float(result.get("confidence", 0))))
    bbox = result.get("bbox_approx") or []
    area = 0.0
    if len(bbox) >= 4:
        width = max(0.0, min(1.0, float(bbox[2])))
        height = max(0.0, min(1.0, float(bbox[3])))
        area = min(1.0, width * height)
    class_weight = {"pothole": 0.78, "deformation": 0.75, "crack": 0.55, "patch": 0.38, "other": 0.50}.get(result.get("type"), 0.35)
    apparent_area = min(1.0, area * 8)
    score = round(0.45 * class_weight + 0.30 * apparent_area + 0.25 * confidence, 3)
    if confidence < 0.35 or result.get("type") == "none":
        return "unknown", score
    if score >= 0.68:
        return "high", score
    if score >= 0.43:
        return "medium", score
    return "low", score
