import base64
import hashlib
import hmac
import os


SCHEME = "scrypt"
N = 2**15
R = 8
P = 1
KEY_LENGTH = 32
MAX_MEMORY = 64 * 1024 * 1024


def validate_password(password: str) -> str | None:
    if len(password) < 8:
        return "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร"
    if not any(character.isalpha() for character in password):
        return "รหัสผ่านต้องมีตัวอักษรอย่างน้อย 1 ตัว"
    if not any(character.isdigit() for character in password):
        return "รหัสผ่านต้องมีตัวเลขอย่างน้อย 1 ตัว"
    return None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=N, r=R, p=P,
        dklen=KEY_LENGTH, maxmem=MAX_MEMORY,
    )
    return "$".join(
        (
            SCHEME,
            str(N),
            str(R),
            str(P),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        )
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n, r, p, salt_text, hash_text = encoded.split("$", 5)
        if scheme != SCHEME:
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(hash_text)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=MAX_MEMORY,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
