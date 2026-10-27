from datetime import datetime, timezone


DEMO_SESSION_ID = "00000000-0000-4000-8000-000000000001"

DEMO = {
    "synthetic": True,
    "message": "Datos sintéticos para mostrar la interfaz. No son detecciones reales.",
    "sessions": [{
        "id": DEMO_SESSION_ID,
        "name": "Recorrido de demostración",
        "status": "completed",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "error_message": None,
        "defects": [
            {
                "id": "10000000-0000-4000-8000-000000000001", "session_id": DEMO_SESSION_ID,
                "defect_type": "pothole", "severity_estimated": "high", "severity_score": 0.79,
                "review_status": "pending", "description": "Depresión amplia visible en la superficie de rodamiento.",
                "first_observed_at": 8.0, "last_observed_at": 10.0, "confidence": 0.91,
                "latitude": -34.60361, "longitude": -58.38154, "evidence_url": None, "is_synthetic": True,
            },
            {
                "id": "10000000-0000-4000-8000-000000000002", "session_id": DEMO_SESSION_ID,
                "defect_type": "crack", "severity_estimated": "medium", "severity_score": 0.51,
                "review_status": "confirmed", "description": "Grieta longitudinal visible; tamaño físico no estimado.",
                "first_observed_at": 22.0, "last_observed_at": 22.0, "confidence": 0.76,
                "latitude": -34.60412, "longitude": -58.37991, "evidence_url": None, "is_synthetic": True,
            },
            {
                "id": "10000000-0000-4000-8000-000000000003", "session_id": DEMO_SESSION_ID,
                "defect_type": "patch", "severity_estimated": "low", "severity_score": 0.34,
                "review_status": "pending", "description": "Reparación previa visible en el pavimento.",
                "first_observed_at": 35.0, "last_observed_at": 37.0, "confidence": 0.68,
                "latitude": -34.60473, "longitude": -58.37818, "evidence_url": None, "is_synthetic": True,
            },
        ],
    }],
}
