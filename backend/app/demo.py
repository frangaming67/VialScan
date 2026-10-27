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
        "analysis_summary": {
            "frames_total": 24,
            "condition_counts": {"good": 12, "fair": 7, "poor": 4, "not_assessable": 1},
            "condition_percentages": {"good": 50.0, "fair": 29.2, "poor": 16.7, "not_assessable": 4.1},
            "defect_observations": 8,
            "consolidated_incidents": 5,
            "category_counts": {"pothole": 2, "transverse_crack": 2, "alligator_crack": 2, "patch": 1, "rutting": 1},
            "severity_counts": {"low": 1, "medium": 3, "high": 4},
        },
        "condition_points": [
            {"frame_id": "20000000-0000-4000-8000-000000000001", "elapsed_seconds": 0, "road_condition": "good", "confidence": 0.89, "summary": "Superficie visible continua; no se aprecian daños claros.", "latitude": -34.60320, "longitude": -58.38240, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000002", "elapsed_seconds": 8, "road_condition": "poor", "confidence": 0.91, "summary": "Bache visible en el carril.", "latitude": -34.60361, "longitude": -58.38154, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000003", "elapsed_seconds": 22, "road_condition": "fair", "confidence": 0.76, "summary": "Grieta transversal aislada.", "latitude": -34.60412, "longitude": -58.37991, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000004", "elapsed_seconds": 36, "road_condition": "good", "confidence": 0.87, "summary": "Pavimento continuo; reparación previa aislada.", "latitude": -34.60473, "longitude": -58.37818, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000005", "elapsed_seconds": 48, "road_condition": "poor", "confidence": 0.88, "summary": "Fisuración interconectada en una zona del carril.", "latitude": -34.60528, "longitude": -58.37662, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000006", "elapsed_seconds": 64, "road_condition": "fair", "confidence": 0.73, "summary": "Ahuellamiento aparente; profundidad no estimada.", "latitude": -34.60582, "longitude": -58.37531, "is_synthetic": True},
        ],
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
                "defect_type": "transverse_crack", "severity_estimated": "medium", "severity_score": 0.51,
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
            {
                "id": "10000000-0000-4000-8000-000000000004", "session_id": DEMO_SESSION_ID,
                "defect_type": "alligator_crack", "severity_estimated": "high", "severity_score": 0.72,
                "review_status": "pending", "description": "Red conectada de grietas poligonales en una zona del carril.",
                "first_observed_at": 48.0, "last_observed_at": 50.0, "confidence": 0.88,
                "latitude": -34.60528, "longitude": -58.37662, "evidence_url": None, "is_synthetic": True,
            },
            {
                "id": "10000000-0000-4000-8000-000000000005", "session_id": DEMO_SESSION_ID,
                "defect_type": "rutting", "severity_estimated": "medium", "severity_score": 0.57,
                "review_status": "pending", "description": "Canales longitudinales visibles en la zona de rodadura; profundidad no estimada.",
                "first_observed_at": 64.0, "last_observed_at": 64.0, "confidence": 0.73,
                "latitude": -34.60582, "longitude": -58.37531, "evidence_url": None, "is_synthetic": True,
            },
        ],
    }],
}
