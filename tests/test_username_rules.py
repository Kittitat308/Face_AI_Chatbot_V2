import unittest

from app.repositories import normalize_identifier, validate_username


class UsernameRuleTests(unittest.TestCase):
    def test_contiguous_username_is_valid(self):
        self.assertIsNone(validate_username("User123"))

    def test_all_whitespace_positions_are_rejected(self):
        for username in (
            " User123", "User 123", "User123 ", "User\t123", "User\u200b123"
        ):
            with self.subTest(username=username):
                self.assertIsNotNone(validate_username(username))

    def test_unicode_is_normalized_without_changing_case(self):
        self.assertEqual(normalize_identifier("  มาร์คคุง  "), "มาร์คคุง")
        self.assertEqual(normalize_identifier("e\u0301"), "é")
        self.assertNotEqual(normalize_identifier("Mark"), normalize_identifier("mark"))


if __name__ == "__main__":
    unittest.main()
