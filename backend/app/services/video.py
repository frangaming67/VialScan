from pathlib import Path

import cv2


def video_duration(video_path: Path) -> float:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("No se pudo abrir el video. Prueba con un MP4 compatible.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    capture.release()
    duration = frame_count / fps if fps > 0 else 0.0
    if duration <= 0:
        raise ValueError("El video no tiene una duración legible.")
    return duration


def extract_frames(video_path: Path, output_dir: Path, interval_seconds: float) -> tuple[list[tuple[float, Path]], float]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError("No se pudo abrir el video. Prueba con un MP4 compatible.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 0
    frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    duration = frame_count / fps if fps > 0 else 0.0
    if duration <= 0:
        capture.release()
        raise ValueError("El video no tiene una duración legible.")
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[tuple[float, Path]] = []
    elapsed = 0.0
    while elapsed < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, elapsed * 1000)
        ok, frame = capture.read()
        if ok:
            frame_path = output_dir / f"frame-{int(elapsed * 1000):08d}.jpg"
            if cv2.imwrite(str(frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82]):
                frames.append((elapsed, frame_path))
        elapsed += max(0.5, interval_seconds)
    capture.release()
    if not frames:
        raise ValueError("No se pudieron extraer fotogramas del video.")
    return frames, duration
