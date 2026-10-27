import json
from pathlib import Path
from datetime import datetime, timezone


DEMO_SESSION_ID = "00000000-0000-4000-8000-000000000001"
DEMO_ROUTE = json.loads((Path(__file__).parent / "data" / "demo_route.json").read_text(encoding="utf-8"))

DEMO = {
    "synthetic": True,
    "message": "Resultados sintéticos para mostrar la interfaz. Las fotos son referencias públicas; no son detecciones reales.",
    "sessions": [{
        "id": DEMO_SESSION_ID,
        "name": "Recorrido de demostración · Mendoza",
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
        "route_segments": DEMO_ROUTE,
        "condition_points": [
            {"frame_id": "20000000-0000-4000-8000-000000000001", "elapsed_seconds": 0, "road_condition": "good", "confidence": 0.89, "summary": "Superficie visible continua; no se aprecian daños claros.", "latitude": -32.891936, "longitude": -68.845169, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000002", "elapsed_seconds": 8, "road_condition": "poor", "confidence": 0.91, "summary": "Bache visible en el carril.", "latitude": -32.889492, "longitude": -68.850043, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000003", "elapsed_seconds": 22, "road_condition": "fair", "confidence": 0.76, "summary": "Grieta transversal aislada.", "latitude": -32.885738, "longitude": -68.846129, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000004", "elapsed_seconds": 36, "road_condition": "good", "confidence": 0.87, "summary": "Pavimento continuo; reparación previa aislada.", "latitude": -32.889930, "longitude": -68.840588, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000005", "elapsed_seconds": 48, "road_condition": "poor", "confidence": 0.88, "summary": "Fisuración interconectada en una zona del carril.", "latitude": -32.895235, "longitude": -68.840575, "is_synthetic": True},
            {"frame_id": "20000000-0000-4000-8000-000000000006", "elapsed_seconds": 64, "road_condition": "fair", "confidence": 0.73, "summary": "Ahuellamiento aparente; profundidad no estimada.", "latitude": -32.896590, "longitude": -68.846548, "is_synthetic": True},
        ],
        "defects": [
            {
                "id": "10000000-0000-4000-8000-000000000001", "session_id": DEMO_SESSION_ID,
                "defect_type": "pothole", "severity_estimated": "high", "severity_score": 0.79,
                "review_status": "pending", "description": "Depresión amplia visible en la superficie de rodamiento.",
                "first_observed_at": 8.0, "last_observed_at": 10.0, "confidence": 0.91,
                "latitude": -32.889492, "longitude": -68.850043, "evidence_url": "/demo-images/pothole.jpg", "is_synthetic": True,
                "evidence_credit": "Frankie Fouganthin · CC BY-SA 4.0", "evidence_source_url": "https://commons.wikimedia.org/wiki/File:Pothole_in_an_asphalt_pavement.jpg",
            },
            {
                "id": "10000000-0000-4000-8000-000000000002", "session_id": DEMO_SESSION_ID,
                "defect_type": "transverse_crack", "severity_estimated": "medium", "severity_score": 0.51,
                "review_status": "confirmed", "description": "Grieta transversal visible; tamaño físico no estimado.",
                "first_observed_at": 22.0, "last_observed_at": 22.0, "confidence": 0.76,
                "latitude": -32.885738, "longitude": -68.846129, "evidence_url": "/demo-images/cracked-asphalt.jpg", "is_synthetic": True,
                "evidence_credit": "Bidgee · CC BY-SA 3.0", "evidence_source_url": "https://commons.wikimedia.org/wiki/File:Cracked_asphalt.jpg",
            },
            {
                "id": "10000000-0000-4000-8000-000000000003", "session_id": DEMO_SESSION_ID,
                "defect_type": "patch", "severity_estimated": "low", "severity_score": 0.34,
                "review_status": "pending", "description": "Reparación previa visible en el pavimento.",
                "first_observed_at": 35.0, "last_observed_at": 37.0, "confidence": 0.68,
                "latitude": -32.889930, "longitude": -68.840588, "evidence_url": "/demo-images/patched-road.jpg", "is_synthetic": True,
                "evidence_credit": "Famartin · CC BY-SA 4.0", "evidence_source_url": "https://commons.wikimedia.org/wiki/File:2018-09-03_15_15_33_Recently_patched_potholes_along_Franklin_Farm_Road_in_the_Franklin_Farm_section_of_Oak_Hill,_Fairfax_County,_Virginia.jpg",
            },
            {
                "id": "10000000-0000-4000-8000-000000000004", "session_id": DEMO_SESSION_ID,
                "defect_type": "alligator_crack", "severity_estimated": "high", "severity_score": 0.72,
                "review_status": "pending", "description": "Red conectada de grietas poligonales en una zona del carril.",
                "first_observed_at": 48.0, "last_observed_at": 50.0, "confidence": 0.88,
                "latitude": -32.895235, "longitude": -68.840575, "evidence_url": "/demo-images/worn-asphalt.jpg", "is_synthetic": True,
                "evidence_credit": "John Harvey · Dominio público", "evidence_source_url": "https://commons.wikimedia.org/wiki/File:Worn_cracked_asphalt_pavement.jpg",
            },
            {
                "id": "10000000-0000-4000-8000-000000000005", "session_id": DEMO_SESSION_ID,
                "defect_type": "rutting", "severity_estimated": "medium", "severity_score": 0.57,
                "review_status": "pending", "description": "Canales longitudinales visibles en la zona de rodadura; profundidad no estimada.",
                "first_observed_at": 64.0, "last_observed_at": 64.0, "confidence": 0.73,
                "latitude": -32.896590, "longitude": -68.846548, "evidence_url": "/demo-images/rutted-road.jpg", "is_synthetic": True,
                "evidence_credit": "Oregon Department of Transportation · CC BY 2.0", "evidence_source_url": "https://commons.wikimedia.org/wiki/File:Rutted_pavement_on_I-405_in_Portland,_OR.jpg",
            },
        ],
    }],
}
