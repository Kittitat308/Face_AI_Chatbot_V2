from dataclasses import dataclass
import threading

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from insightface.app.common import Face

from app.config import settings
from app.repositories import get_all_face_embeddings


DETECTION_THRESHOLD = 0.45
FACE_MATCH_THRESHOLD = 0.50
SWITCH_MATCH_THRESHOLD = 0.55
DETECTION_SIZE = (640, 640)


@dataclass(frozen=True)
class FaceScanResult:
    face_count: int
    current_user_found: bool
    recognized_user: object | None = None
    recognized_score: float = -1.0
    unknown_face_found: bool = False


class FaceService:
    """InsightFace wrapper with an application-wide in-memory embedding cache."""

    _cache_lock = threading.RLock()
    _cache_loaded = False
    _cached_users = {}
    _cached_embeddings = {}

    def __init__(self):
        self.last_error = ""
        self._ensure_embedding_cache()
        self.model = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
            allowed_modules=["detection", "recognition"],
        )
        self.model.prepare(
            ctx_id=0,
            det_thresh=DETECTION_THRESHOLD,
            det_size=DETECTION_SIZE,
        )
        self.recognition_model = self.model.models["recognition"]

    @staticmethod
    def normalize(embedding):
        embedding = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(embedding)
        return embedding if norm == 0 else embedding / norm

    @classmethod
    def _ensure_embedding_cache(cls):
        with cls._cache_lock:
            if cls._cache_loaded:
                return
            cls._load_embedding_cache_locked()

    @classmethod
    def _load_embedding_cache_locked(cls):
        users = {}
        embeddings = {}
        for user, embedding in get_all_face_embeddings():
            users[user.id] = user
            embeddings.setdefault(user.id, []).append(cls.normalize(embedding))
        cls._cached_users = users
        cls._cached_embeddings = embeddings
        cls._cache_loaded = True

    @classmethod
    def refresh_embedding_cache(cls):
        with cls._cache_lock:
            cls._load_embedding_cache_locked()

    @classmethod
    def cache_embedding(cls, user, embedding):
        normalized = cls.normalize(embedding).copy()
        with cls._cache_lock:
            cls._cached_users[user.id] = user
            cls._cached_embeddings.setdefault(user.id, []).append(normalized)
            cls._cache_loaded = True

    @classmethod
    def update_cached_user(cls, user):
        with cls._cache_lock:
            if user.id in cls._cached_embeddings:
                cls._cached_users[user.id] = user

    @classmethod
    def _cache_snapshot(cls):
        cls._ensure_embedding_cache()
        with cls._cache_lock:
            return dict(cls._cached_users), {
                user_id: tuple(items)
                for user_id, items in cls._cached_embeddings.items()
            }

    @staticmethod
    def _score_user(embedding, user_id, embeddings):
        scores = [
            float(np.dot(embedding, stored))
            for stored in embeddings.get(user_id, ())
        ]
        return max(scores, default=-1.0)

    @classmethod
    def _identify_from_cache(cls, embedding, threshold, users, embeddings):
        best_user = None
        best_score = -1.0
        for user_id, stored_items in embeddings.items():
            for stored in stored_items:
                score = float(np.dot(embedding, stored))
                if score > best_score:
                    best_score = score
                    best_user = users.get(user_id)
        if best_user is not None and best_score >= threshold:
            return best_user, best_score
        return None, best_score

    def extract_embedding(self, frame):
        bboxes, keypoints = self.model.det_model.detect(frame)
        if bboxes.shape[0] == 0:
            self.last_error = "ไม่พบใบหน้า"
            return None, None
        largest_index = max(
            range(bboxes.shape[0]),
            key=lambda index: (bboxes[index, 2] - bboxes[index, 0])
            * (bboxes[index, 3] - bboxes[index, 1]),
        )
        face = self._recognize_detected_face(
            frame, bboxes, keypoints, largest_index
        )
        self.last_error = ""
        return self.normalize(face.embedding), face

    def _recognize_detected_face(self, frame, bboxes, keypoints, index):
        keypoint = None if keypoints is None else keypoints[index]
        face = Face(
            bbox=bboxes[index, 0:4],
            kps=keypoint,
            det_score=bboxes[index, 4],
        )
        self.recognition_model.get(frame, face)
        return face

    def identify(self, embedding, threshold=None):
        if embedding is None:
            return None, 0.0
        users, embeddings = self._cache_snapshot()
        return self._identify_from_cache(
            self.normalize(embedding),
            settings.face_match_threshold if threshold is None else threshold,
            users,
            embeddings,
        )

    def matches_user(self, embedding, user_id, threshold=None):
        if embedding is None:
            return False, 0.0
        _, embeddings = self._cache_snapshot()
        score = self._score_user(self.normalize(embedding), user_id, embeddings)
        required = FACE_MATCH_THRESHOLD if threshold is None else threshold
        return score >= required, score

    def analyze_session_frame(self, frame, current_user_id):
        """Apply the post-login priority rules using one model inference."""
        bboxes, keypoints = self.model.det_model.detect(frame)
        face_count = int(bboxes.shape[0])
        if face_count == 0:
            return FaceScanResult(face_count=0, current_user_found=False)

        users, embeddings = self._cache_snapshot()
        normalized_faces = []

        # Current user has absolute priority. Stop comparisons as soon as found.
        for index in range(face_count):
            face = self._recognize_detected_face(
                frame, bboxes, keypoints, index
            )
            embedding = self.normalize(face.embedding)
            normalized_faces.append(embedding)
            current_score = self._score_user(
                embedding, current_user_id, embeddings
            )
            if current_score >= FACE_MATCH_THRESHOLD:
                return FaceScanResult(
                    face_count=face_count,
                    current_user_found=True,
                    recognized_user=users.get(current_user_id),
                    recognized_score=current_score,
                )

        # Current user was not found. Classify every detected face only far
        # enough to distinguish "contains unknown" from "all registered";
        # never select an account-switch candidate from a multi-face frame.
        if face_count >= 2:
            unknown_face_found = any(
                self._identify_from_cache(
                    embedding,
                    SWITCH_MATCH_THRESHOLD,
                    users,
                    embeddings,
                )[0]
                is None
                for embedding in normalized_faces
            )
            return FaceScanResult(
                face_count=face_count,
                current_user_found=False,
                unknown_face_found=unknown_face_found,
            )

        recognized_user, score = self._identify_from_cache(
            normalized_faces[0],
            SWITCH_MATCH_THRESHOLD,
            users,
            embeddings,
        )
        return FaceScanResult(
            face_count=1,
            current_user_found=False,
            recognized_user=recognized_user,
            recognized_score=score,
        )

    @staticmethod
    def draw_face_box(frame, face):
        if face is None:
            return frame
        x1, y1, x2, y2 = (int(value) for value in face.bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 200, 120), 2)
        return frame
