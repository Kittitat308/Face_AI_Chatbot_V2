import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.services.face_service import FaceService


class FaceCacheTests(unittest.TestCase):
    def setUp(self):
        self.original_loaded = FaceService._cache_loaded
        self.original_users = FaceService._cached_users
        self.original_embeddings = FaceService._cached_embeddings
        FaceService._cache_loaded = False
        FaceService._cached_users = {}
        FaceService._cached_embeddings = {}

    def tearDown(self):
        FaceService._cache_loaded = self.original_loaded
        FaceService._cached_users = self.original_users
        FaceService._cached_embeddings = self.original_embeddings

    def test_database_is_loaded_only_once(self):
        user = SimpleNamespace(id=1)
        rows = [(user, np.array([1.0, 0.0], dtype=np.float32))]
        with patch("app.services.face_service.get_all_face_embeddings", return_value=rows) as query:
            FaceService._ensure_embedding_cache()
            FaceService._ensure_embedding_cache()
        self.assertEqual(query.call_count, 1)

    def test_new_embedding_updates_shared_cache(self):
        user = SimpleNamespace(id=9)
        FaceService.cache_embedding(user, np.array([0.0, 2.0]))
        cached = FaceService._cached_embeddings[user.id][0]
        np.testing.assert_allclose(cached, np.array([0.0, 1.0]))
        self.assertIs(FaceService._cached_users[user.id], user)

    def make_service(self, face_embeddings):
        bboxes = np.array(
            [[index * 20, 0, index * 20 + 10, 10, 0.99]
             for index in range(len(face_embeddings))],
            dtype=np.float32,
        )

        class Detector:
            def detect(self, frame):
                return bboxes, None

        class Recognition:
            def __init__(self, values):
                self.values = list(values)

            def get(self, frame, face):
                face.embedding = self.values.pop(0)

        service = FaceService.__new__(FaceService)
        service.model = SimpleNamespace(det_model=Detector())
        service.recognition_model = Recognition(face_embeddings)
        return service

    def seed_two_users(self):
        user_a = SimpleNamespace(id=1)
        user_b = SimpleNamespace(id=2)
        FaceService._cache_loaded = True
        FaceService._cached_users = {1: user_a, 2: user_b}
        FaceService._cached_embeddings = {
            1: [np.array([1.0, 0.0], dtype=np.float32)],
            2: [np.array([0.0, 1.0], dtype=np.float32)],
        }
        return user_a, user_b

    def test_multi_face_current_user_has_priority(self):
        user_a, _ = self.seed_two_users()
        for companion in (
            np.array([0.0, 1.0]),
            np.array([-1.0, 0.0]),
        ):
            with self.subTest(companion=companion):
                service = self.make_service(
                    [companion, np.array([1.0, 0.0])]
                )
                result = service.analyze_session_frame(
                    np.zeros((10, 10, 3)),
                    user_a.id,
                )
                self.assertEqual(result.face_count, 2)
                self.assertTrue(result.current_user_found)

    def test_multiple_with_unknown_is_reported_without_account_choice(self):
        user_a, _ = self.seed_two_users()
        service = self.make_service(
            [np.array([0.0, 1.0]), np.array([-1.0, 0.0])]
        )
        result = service.analyze_session_frame(np.zeros((10, 10, 3)), user_a.id)
        self.assertEqual(result.face_count, 2)
        self.assertFalse(result.current_user_found)
        self.assertIsNone(result.recognized_user)
        self.assertTrue(result.unknown_face_found)

    def test_multiple_registered_others_has_no_unknown(self):
        user_a, user_b = self.seed_two_users()
        user_c = SimpleNamespace(id=3)
        FaceService._cached_users[user_c.id] = user_c
        FaceService._cached_embeddings[user_c.id] = [
            np.array([-1.0, 0.0], dtype=np.float32)
        ]
        service = self.make_service(
            [np.array([0.0, 1.0]), np.array([-1.0, 0.0])]
        )
        result = service.analyze_session_frame(
            np.zeros((10, 10, 3)),
            user_a.id,
        )
        self.assertFalse(result.current_user_found)
        self.assertIsNone(result.recognized_user)
        self.assertFalse(result.unknown_face_found)

    def test_single_registered_other_uses_switch_recognition(self):
        user_a, user_b = self.seed_two_users()
        service = self.make_service([np.array([0.0, 1.0])])
        result = service.analyze_session_frame(np.zeros((10, 10, 3)), user_a.id)
        self.assertFalse(result.current_user_found)
        self.assertEqual(result.recognized_user.id, user_b.id)


if __name__ == "__main__":
    unittest.main()
