import hashlib
import hmac
import os

from fastapi import Request


HASH_NAME = "sha256"
ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_{HASH_NAME}${ITERATIONS}${salt.hex()}${password_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, hash_hex = stored_hash.split("$", 3)
        hash_name = algorithm.replace("pbkdf2_", "")
        candidate = hashlib.pbkdf2_hmac(
            hash_name,
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate.hex(), hash_hex)


def login_user(request: Request, user_id: int) -> None:
    request.session.clear()
    request.session["user_id"] = user_id


def logout_user(request: Request) -> None:
    request.session.clear()
