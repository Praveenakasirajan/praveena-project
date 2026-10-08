"""
video_analyzer.py - Video and facial expression analysis for AI Interview Coach.
Performs face detection, eye contact tracking, look-away event detection with timestamps,
head stability measurement, and visual confidence scoring.
"""

import logging
import math
import os
import statistics
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from mediapipe_compat import get_cascade_path

logger = logging.getLogger(__name__)

# Minimum duration (in seconds) of continuous looking away to count as a real event.
# Prevents normal blinks, slight saccades, and single-frame detection noise from triggering false positives.
LOOK_AWAY_MIN_SECONDS = 1.0

# Tolerance gap (in seconds) of camera-facing frames before closing a look-away event.
# If someone looks away, blinks for 0.3s, and continues looking away, it remains ONE continuous event.
LOOK_AWAY_GAP_TOLERANCE_SECONDS = 0.6

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS string."""
    seconds = max(0.0, float(seconds))
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def _empty_video_metrics(**extra) -> Dict:
    """Return default empty metrics dictionary."""
    metrics = {
        "total_frames": 0,
        "face_frames": 0,
        "face_visible_percent": 0.0,
        "look_away_count": 0,
        "look_away_events": [],
        "total_look_away_duration": 0.0,
        "eye_contact_score": 0.0,
        "head_stability_score": 0.0,
        "visual_confidence_score": 0.0,
    }
    metrics.update(extra)
    return metrics


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: List[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _detect_face_and_gaze(
    frame,
    face_classifier,
    eye_classifier,
) -> Optional[Dict]:
    """
    Detect face and estimate head orientation and eye gaze for a single frame.
    Returns None if no face detected.
    """
    frame_h, frame_w = frame.shape[:2]
    if frame_h <= 0 or frame_w <= 0:
        return None

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    eq_gray = cv2.equalizeHist(gray)

    # Detect faces
    faces = face_classifier.detectMultiScale(
        eq_gray,
        scaleFactor=1.1,
        minNeighbors=4,
        minSize=(max(30, int(frame_w * 0.08)), max(30, int(frame_h * 0.08))),
    )

    if len(faces) == 0:
        return None

    # Pick the largest face (by area w*h) to ignore clothes/background false positives
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    fx, fy, fw, fh = faces[0]

    # Relative coordinates (0.0 to 1.0)
    center_x = (fx + (fw / 2.0)) / frame_w
    center_y = (fy + (fh / 2.0)) / frame_h
    rel_area = (fw * fh) / (frame_w * frame_h)
    aspect_ratio = fw / fh if fh else 1.0

    # Head yaw & pitch estimation
    horizontal_offset = center_x - 0.5
    vertical_offset = center_y - 0.5
    yaw_from_center = horizontal_offset * 90.0
    yaw_from_shape = _clamp((aspect_ratio - 0.82) * 45.0, -18.0, 18.0)
    yaw = yaw_from_center + yaw_from_shape
    pitch = _clamp(vertical_offset * 60.0, -25.0, 25.0)

    # Eye gaze analysis in upper 58% of face
    eye_gaze = "center"
    upper_h = max(1, int(fh * 0.58))
    upper_face = gray[fy : fy + upper_h, fx : fx + fw]

    if eye_classifier is not None and upper_face.size > 0:
        eq_upper = cv2.equalizeHist(upper_face)
        eyes = eye_classifier.detectMultiScale(
            eq_upper,
            scaleFactor=1.05,
            minNeighbors=3,
            minSize=(max(10, int(fw * 0.08)), max(8, int(fh * 0.06))),
        )

        if len(eyes) >= 2:
            # Sort eyes left-to-right
            eyes = sorted(eyes, key=lambda e: e[0])[:2]
            eye_pair_cx = _mean([(e[0] + e[2] / 2.0) / fw for e in eyes])
            eye_pair_cy = _mean([(e[1] + e[3] / 2.0) / fh for e in eyes])

            if eye_pair_cx < 0.38:
                eye_gaze = "left"
            elif eye_pair_cx > 0.62:
                eye_gaze = "right"
            elif eye_pair_cy > 0.44:
                eye_gaze = "down"
            elif eye_pair_cy < 0.25:
                eye_gaze = "up"
            else:
                eye_gaze = "center"
        elif len(eyes) == 1:
            # Single eye: check if head is significantly turned
            if yaw < -16.0 or center_x < 0.38:
                eye_gaze = "left"
            elif yaw > 16.0 or center_x > 0.62:
                eye_gaze = "right"
            else:
                # Normal head posture with 1 eye detected = transient blink / shadow -> keep center
                eye_gaze = "center"
        else:
            # 0 eyes: if head is turned, it's away; otherwise could be blink
            if abs(yaw) > 18.0 or abs(horizontal_offset) > 0.16:
                eye_gaze = "left" if yaw < 0 else "right"
            elif pitch > 18.0 or center_y > 0.65:
                eye_gaze = "down"
            elif pitch < -18.0 or center_y < 0.30:
                eye_gaze = "up"
            else:
                eye_gaze = "center"

    # Evaluate overall looking-away condition for this frame
    is_away = False
    direction = "Center"

    if abs(yaw) > 20.0 or abs(horizontal_offset) > 0.18:
        is_away = True
        direction = "Left" if (horizontal_offset < 0 or yaw < 0) else "Right"
    elif pitch > 18.0 or center_y > 0.65:
        is_away = True
        direction = "Down"
    elif pitch < -18.0 or center_y < 0.28:
        is_away = True
        direction = "Up"
    elif eye_gaze in {"left", "right", "down", "up"}:
        is_away = True
        direction = eye_gaze.capitalize()

    return {
        "center_x": center_x,
        "center_y": center_y,
        "area": rel_area,
        "yaw": round(yaw, 1),
        "pitch": round(pitch, 1),
        "eye_gaze": eye_gaze,
        "is_away": is_away,
        "direction": direction,
    }


def analyze_video(video_path: str) -> Dict:
    """
    Analyze video file for face detection, eye contact, and look-away events.
    Returns structured analysis metrics with timestamps.
    """
    if not os.path.exists(video_path):
        return _empty_video_metrics(error="File not found")

    file_ext = Path(video_path).suffix.lower()
    if file_ext in AUDIO_EXTENSIONS:
        return _empty_video_metrics(status="skipped", reason="audio_only_file")

    if file_ext not in VIDEO_EXTENSIONS:
        return _empty_video_metrics(
            error=f"Not a supported video format ({file_ext})"
        )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return _empty_video_metrics(error="Could not open video file")

    raw_fps = cap.get(cv2.CAP_PROP_FPS)
    fps = raw_fps if (raw_fps and 1.0 <= raw_fps <= 120.0) else 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if width <= 0 or height <= 0:
        cap.release()
        return _empty_video_metrics(status="skipped", reason="audio_only_file")

    # Load cascade classifiers
    face_cascade_path = get_cascade_path("haarcascade_frontalface_default.xml")
    eye_cascade_path = get_cascade_path("haarcascade_eye.xml")
    face_classifier = cv2.CascadeClassifier(face_cascade_path)
    eye_classifier = cv2.CascadeClassifier(eye_cascade_path)

    if face_classifier.empty():
        cap.release()
        logger.error("Could not load face cascade classifier: %s", face_cascade_path)
        return _empty_video_metrics(error="Face detection model not available")

    # Performance optimization:
    # Process at ~12-15 FPS so 30-second videos analyze in ~1 second rather than 30 seconds.
    frame_step = max(1, round(fps / 12.0))
    effective_fps = fps / frame_step

    # Frame resize target for fast detection: max width 640
    target_w = min(640, width)
    scale = target_w / width if width > target_w else 1.0

    total_frames = 0
    analyzed_frames = 0
    face_frames = 0
    direct_face_frames = 0
    face_positions = []

    # Look-away event tracking state machine
    look_away_events = []
    current_event = None  # Dict with start_time, last_away_time, directions
    tolerance_frames = int(effective_fps * LOOK_AWAY_GAP_TOLERANCE_SECONDS)
    gap_counter = 0

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        total_frames += 1

        # Sample every Nth frame for fast processing
        if (frame_idx - 1) % frame_step != 0:
            continue

        analyzed_frames += 1
        current_time = (frame_idx - 1) / fps

        # Resize if large
        if scale < 1.0:
            frame_resized = cv2.resize(frame, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
        else:
            frame_resized = frame

        detection = _detect_face_and_gaze(
            frame_resized,
            face_classifier,
            eye_classifier if not eye_classifier.empty() else None,
        )

        if detection is not None:
            face_frames += 1
            face_positions.append({
                "center_x": detection["center_x"],
                "center_y": detection["center_y"],
                "area": detection["area"],
            })

            is_away = detection["is_away"]
            direction = detection["direction"]

            if not is_away:
                direct_face_frames += 1
        else:
            # Face absent in this frame
            # Only treat as looking away if candidate was previously confirmed present on screen
            if face_frames > 0:
                is_away = True
                direction = "Away"
            else:
                is_away = False
                direction = "None"

        # -------------------------------------------------------------
        # Temporal State Machine for Look-Away Events
        # -------------------------------------------------------------
        if is_away and face_frames > 0:
            gap_counter = 0
            if current_event is None:
                # Start a new pending look-away event
                current_event = {
                    "start_time": current_time,
                    "last_away_time": current_time,
                    "directions": [direction],
                }
            else:
                # Continue the existing look-away event
                current_event["last_away_time"] = current_time
                current_event["directions"].append(direction)
        else:
            # Looking towards camera or face not yet detected
            if current_event is not None:
                gap_counter += 1
                if gap_counter >= tolerance_frames:
                    # Look-away event has concluded
                    duration = current_event["last_away_time"] - current_event["start_time"]
                    if duration >= LOOK_AWAY_MIN_SECONDS:
                        # Find most frequent non-generic direction if available
                        dirs = [d for d in current_event["directions"] if d != "Away"] or current_event["directions"]
                        primary_dir = max(set(dirs), key=dirs.count) if dirs else "Away"
                        look_away_events.append({
                            "event_num": len(look_away_events) + 1,
                            "start_time": format_timestamp(current_event["start_time"]),
                            "end_time": format_timestamp(current_event["last_away_time"]),
                            "duration": round(duration, 1),
                            "direction": primary_dir,
                            "start_seconds": round(current_event["start_time"], 2),
                            "end_seconds": round(current_event["last_away_time"], 2),
                        })
                    current_event = None
                    gap_counter = 0

    cap.release()

    video_duration = total_frames / fps if fps else 0.0

    # If an event was still in progress when the video ended, finalize it
    if current_event is not None and face_frames > 0:
        duration = current_event["last_away_time"] - current_event["start_time"]
        if duration >= LOOK_AWAY_MIN_SECONDS:
            dirs = [d for d in current_event["directions"] if d != "Away"] or current_event["directions"]
            primary_dir = max(set(dirs), key=dirs.count) if dirs else "Away"
            look_away_events.append({
                "event_num": len(look_away_events) + 1,
                "start_time": format_timestamp(current_event["start_time"]),
                "end_time": format_timestamp(current_event["last_away_time"]),
                "duration": round(duration, 1),
                "direction": primary_dir,
                "start_seconds": round(current_event["start_time"], 2),
                "end_seconds": round(current_event["last_away_time"], 2),
            })

    # If no face was ever detected, never invent look away events or false confidence
    if face_frames == 0:
        look_away_events = []

    total_look_away_duration = round(sum(ev["duration"] for ev in look_away_events), 1)
    look_away_count = len(look_away_events)

    # -------------------------------------------------------------
    # Metrics Calculation
    # -------------------------------------------------------------
    if analyzed_frames == 0:
        return _empty_video_metrics()

    face_visible_percent = round((face_frames / analyzed_frames) * 100.0, 1)

    if face_frames == 0:
        return {
            "total_frames": total_frames,
            "analyzed_frames": analyzed_frames,
            "face_frames": 0,
            "video_duration_seconds": round(video_duration, 2),
            "face_visible_percent": 0.0,
            "look_away_count": 0,
            "look_away_events": [],
            "total_look_away_duration": 0.0,
            "eye_contact_score": None,
            "head_stability_score": None,
            "visual_confidence_score": 0.0,
            "status": "insufficient_evidence",
            "insufficient_evidence": True,
            "note": "Insufficient visual evidence: No face detected in video. Ensure camera is facing candidate with adequate lighting.",
        }

    # Eye contact score: ratio of direct camera facing to face visible frames
    raw_eye_contact = direct_face_frames / face_frames
    eye_contact_score = round(raw_eye_contact * 10.0, 1)

    # Head stability score: measured by center jitter and area variation
    if len(face_positions) < 2:
        head_stability_score = 10.0
    else:
        centers_x = [p["center_x"] for p in face_positions]
        centers_y = [p["center_y"] for p in face_positions]
        areas = [p["area"] for p in face_positions]

        frame_steps = [
            math.hypot(
                face_positions[i]["center_x"] - face_positions[i - 1]["center_x"],
                face_positions[i]["center_y"] - face_positions[i - 1]["center_y"],
            )
            for i in range(1, len(face_positions))
        ]
        avg_step = _mean(frame_steps)
        center_jitter = math.hypot(_stddev(centers_x), _stddev(centers_y))
        avg_area = _mean(areas)
        area_jitter = _stddev(areas) / avg_area if avg_area else 0.0

        instability = min(
            1.0,
            (avg_step / 0.08 * 0.4) + (center_jitter / 0.18 * 0.4) + (area_jitter / 0.3 * 0.2),
        )
        head_stability_score = round(_clamp((1.0 - instability) * 10.0, 0.0, 10.0), 1)

    # Visual confidence score: weighted combination
    raw_conf = (
        (face_visible_percent / 100.0 * 10.0 * 0.35)
        + (eye_contact_score * 0.40)
        + (head_stability_score * 0.25)
    )
    visual_confidence_score = round(_clamp(raw_conf, 0.0, 10.0), 1)

    result = {
        "total_frames": total_frames,
        "analyzed_frames": analyzed_frames,
        "face_frames": face_frames,
        "video_duration_seconds": round(video_duration, 2),
        "face_visible_percent": face_visible_percent,
        "look_away_count": look_away_count,
        "look_away_events": look_away_events,
        "total_look_away_duration": total_look_away_duration,
        "eye_contact_score": eye_contact_score,
        "head_stability_score": head_stability_score,
        "visual_confidence_score": visual_confidence_score,
        "status": "success",
        "insufficient_evidence": False,
    }

    if face_visible_percent < 20.0:
        result["status"] = "low_confidence"
        result["note"] = "Low face visibility (<20%). Visual evidence is limited; metrics may be imprecise."

    logger.info(
        "Video analysis: face_visible=%s%%, look_away_count=%s, eye_contact=%s/10, head_stability=%s/10, confidence=%s/10",
        face_visible_percent,
        look_away_count,
        eye_contact_score,
        head_stability_score,
        visual_confidence_score,
    )

    return result


# Public alias
analyze_interview_video = analyze_video
