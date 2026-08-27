import unittest

from app.services.password_service import hash_password, validate_password, verify_password


class PasswordServiceTests(unittest.TestCase):
    def test_hash_and_verify(self):
        encoded = hash_password("SecurePass123")
        self.assertTrue(verify_password("SecurePass123", encoded))
        self.assertFalse(verify_password("wrong", encoded))
        self.assertNotIn("SecurePass123", encoded)

    def test_password_policy(self):
        self.assertIsNotNone(validate_password("short"))
        self.assertIsNotNone(validate_password("onlyletters"))
        self.assertIsNone(validate_password("Goodpass1"))


if __name__ == "__main__":
    unittest.main()
