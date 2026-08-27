import cv2
import numpy as np

from insightface.app import FaceAnalysis

from app.config import settings
from app.repositories import get_all_face_embeddings


class FaceService:

    def __init__(self):

        self.last_error = ""

        self.model = FaceAnalysis(
            name="buffalo_l",
            providers=[
                "CPUExecutionProvider"
            ],
        )

        self.model.prepare(
            ctx_id=0,
            det_size=(640, 640),
        )


    @staticmethod
    def normalize(
        embedding,
    ):

        embedding = np.asarray(
            embedding,
            dtype=np.float32,
        )

        norm = np.linalg.norm(
            embedding
        )

        if norm == 0:
            return embedding

        return embedding / norm


    def extract_embedding(
        self,
        frame,
    ):

        faces = self.model.get(
            frame
        )

        if not faces:
            self.last_error = "ไม่พบใบหน้า"
            return None, None

        face = max(
            faces,
            key=lambda item:
                (
                    item.bbox[2] - item.bbox[0]
                )
                *
                (
                    item.bbox[3] - item.bbox[1]
                ),
        )

        self.last_error = ""
        embedding = self.normalize(
            face.embedding
        )

        return embedding, face


    def identify(
        self,
        embedding,
    ):

        if embedding is None:
            return None, 0.0

        best_user = None
        best_score = -1.0

        stored_faces = (
            get_all_face_embeddings()
        )

        for user, stored_embedding in stored_faces:

            stored_embedding = self.normalize(
                stored_embedding
            )

            score = float(
                np.dot(
                    embedding,
                    stored_embedding,
                )
            )

            if score > best_score:
                best_score = score
                best_user = user

        if (
            best_user is not None
            and best_score
            >= settings.face_match_threshold
        ):

            return (
                best_user,
                best_score,
            )

        return (
            None,
            best_score,
        )


    def matches_user(self, embedding, user_id):
        if embedding is None:
            return False, 0.0
        scores = []
        for user, stored_embedding in get_all_face_embeddings():
            if user.id == user_id:
                scores.append(float(np.dot(embedding, self.normalize(stored_embedding))))
        score = max(scores, default=-1.0)
        return score >= settings.face_match_threshold, score


    @staticmethod
    def draw_face_box(
        frame,
        face,
    ):

        if face is None:
            return frame

        x1, y1, x2, y2 = (
            int(value)
            for value in face.bbox
        )

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (80, 200, 120),
            2,
        )

        return frame
