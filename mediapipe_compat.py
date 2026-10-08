from types import SimpleNamespace
from pathlib import Path
import os


def get_cascade_path(filename: str) -> str:
    """Find cascade XML file in project data/cascades directory or cv2.data."""
    local_path = Path(__file__).resolve().parent / "data" / "cascades" / filename
    if local_path.exists():
        return str(local_path)

    import cv2
    if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
        cv2_path = os.path.join(cv2.data.haarcascades, filename)
        if os.path.exists(cv2_path):
            return cv2_path

    return str(local_path)


def ensure_mediapipe_solutions_compat(mp):
    """Expose the legacy mp.solutions.face_detection API when it is absent."""
    if hasattr(mp, "solutions"):
        return mp

    mp.solutions = SimpleNamespace(
        face_detection=SimpleNamespace(FaceDetection=_OpenCVFaceDetection)
    )
    return mp


class _OpenCVFaceDetection:
    def __init__(self, min_detection_confidence=0.5, model_selection=0):
        self.min_detection_confidence = min_detection_confidence
        self.model_selection = model_selection
        self._classifier = None

    def __enter__(self):
        self._load_classifier()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._classifier = None
        return False

    def process(self, image):
        self._load_classifier()

        import cv2

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        faces = self._classifier.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
        )

        detections = [
            SimpleNamespace(
                location_data=SimpleNamespace(
                    relative_bounding_box=SimpleNamespace(
                        xmin=x / image.shape[1],
                        ymin=y / image.shape[0],
                        width=w / image.shape[1],
                        height=h / image.shape[0],
                    )
                )
            )
            for (x, y, w, h) in faces
        ]
        return SimpleNamespace(detections=detections or None)

    def _load_classifier(self):
        if self._classifier is not None:
            return

        import cv2

        cascade_path = get_cascade_path("haarcascade_frontalface_default.xml")
        classifier = cv2.CascadeClassifier(cascade_path)
        if classifier.empty():
            raise RuntimeError(f"Could not load OpenCV face cascade: {cascade_path}")

        self._classifier = classifier

