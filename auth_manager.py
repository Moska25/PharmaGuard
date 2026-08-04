"""
Authentication helper for PharmaGuard.

Passwords are stored as salted PBKDF2-HMAC-SHA256 digests in the format:

    pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>

Accounts created before v1.1 stored a bare, unsalted SHA-256 hex digest. Those
are still accepted at login so existing installations keep working, and each one
is transparently re-hashed to PBKDF2 the next time that account signs in
successfully. See ``needs_rehash``.

Admin credentials are read from the environment rather than baked into source.
"""

import hashlib
import hmac
import os
import re
import secrets
import string
from typing import Optional

from database import DatabaseManager
from user import User

# PBKDF2 cost. Login happens once per session, so a high iteration count is
# cheap for us and expensive for anyone brute-forcing a stolen database.
PBKDF2_ITERATIONS = 240_000
PBKDF2_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16

# A legacy hash is exactly 64 lowercase hex characters and nothing else.
_LEGACY_SHA256_PATTERN = re.compile(r"\A[0-9a-f]{64}\Z")

# Used only when PHARMAGUARD_ADMIN_PASSWORD is not set, so the app stays
# runnable out of the box for reviewers. Never use this for real patient data.
DEMO_ADMIN_USERNAME = "Admin1"
DEMO_ADMIN_PASSWORD = "PharmaGuard!Demo1"


def validate_password(password: str) -> tuple:
    """Validate a password and return (is_valid, message)."""
    missing_requirements = []

    if len(password) < 8:
        missing_requirements.append("Minimum 8 characters")
    if not any(character.isupper() for character in password):
        missing_requirements.append("At least 1 uppercase letter (A-Z)")
    if not any(character.islower() for character in password):
        missing_requirements.append("At least 1 lowercase letter (a-z)")
    if not any(character.isdigit() for character in password):
        missing_requirements.append("At least 1 number (0-9)")
    if not any(character in string.punctuation for character in password):
        missing_requirements.append("At least 1 special character, such as ! @ # $ % ^ & * ( ) _ + - =")

    if missing_requirements:
        return False, "Password must include:\n- " + "\n- ".join(missing_requirements)
    return True, ""


def generate_temporary_password(length: int = 14) -> str:
    """
    Build a random password that satisfies the policy above.

    Used for administrator-initiated resets. A fixed reset string would mean every
    reset account shares one publicly-known password until the patient changes it.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if validate_password(candidate)[0]:
            return candidate


class AuthManager:
    """Handles admin and patient authentication."""

    INACTIVE_MESSAGE = "Your account has been deactivated. Please contact the administrator."

    def __init__(self, database_manager: DatabaseManager) -> None:
        self.database_manager = database_manager
        self.last_login_error = ""
        self.admin_username = os.environ.get("PHARMAGUARD_ADMIN_USER", DEMO_ADMIN_USERNAME)
        self._admin_password = os.environ.get("PHARMAGUARD_ADMIN_PASSWORD", "")
        # Surfaced on the login screen so a demo install is never mistaken for
        # a hardened one.
        self.using_demo_admin = not self._admin_password
        if self.using_demo_admin:
            self._admin_password = DEMO_ADMIN_PASSWORD

    # ------------------------------------------------------------------
    # Password hashing
    # ------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
        """Hash a password with salted PBKDF2-HMAC-SHA256."""
        if salt is None:
            salt = secrets.token_bytes(_SALT_BYTES)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

    @staticmethod
    def _hash_legacy(password: str) -> str:
        """Reproduce the pre-v1.1 unsalted SHA-256 digest, for verification only."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def verify_password(cls, password: str, password_hash: str) -> bool:
        """Return True when password matches the stored hash, old format or new."""
        if not password_hash:
            return False

        if _LEGACY_SHA256_PATTERN.match(password_hash):
            return hmac.compare_digest(cls._hash_legacy(password), password_hash)

        try:
            algorithm, iterations, salt_hex, digest_hex = password_hash.split("$")
            if algorithm != PBKDF2_ALGORITHM:
                return False
            computed = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            )
        except (ValueError, TypeError):
            # Malformed hash: treat as a failed login rather than crashing the app.
            return False
        return hmac.compare_digest(computed.hex(), digest_hex)

    @staticmethod
    def needs_rehash(password_hash: str) -> bool:
        """Return True when a stored hash should be upgraded to current parameters."""
        if _LEGACY_SHA256_PATTERN.match(password_hash or ""):
            return True
        parts = (password_hash or "").split("$")
        if len(parts) != 4 or parts[0] != PBKDF2_ALGORITHM:
            return True
        try:
            return int(parts[1]) < PBKDF2_ITERATIONS
        except ValueError:
            return True

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login_admin(self, username: str, password: str) -> Optional[User]:
        """Validate admin credentials."""
        self.last_login_error = ""
        username_ok = hmac.compare_digest(username, self.admin_username)
        password_ok = hmac.compare_digest(password, self._admin_password)
        if username_ok and password_ok:
            return User(
                user_id=None,
                first_name="Admin",
                last_name="",
                username=self.admin_username,
                password="",
                role=User.ROLE_ADMIN,
            )
        return None

    def login_user(self, username: str, password: str) -> Optional[User]:
        """Validate a patient account from the database."""
        self.last_login_error = ""
        user = self.database_manager.get_user_by_username(username)
        if user and not user.is_active:
            self.last_login_error = self.INACTIVE_MESSAGE
            return None
        if user and self.verify_password(password, user.password):
            self._upgrade_hash_if_needed(user, password)
            return user
        return None

    def _upgrade_hash_if_needed(self, user: User, password: str) -> None:
        """Re-hash a legacy or under-strength password after a successful login."""
        if user.user_id is None or not self.needs_rehash(user.password):
            return
        upgraded = self.hash_password(password)
        self.database_manager.update_user_password(user.user_id, upgraded)
        user.password = upgraded

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------
    def create_patient_user(self, first_name: str, last_name: str, password: str) -> User:
        """Create a patient account with a generated username."""
        valid, message = validate_password(password)
        if not valid:
            raise ValueError(message)
        return self.database_manager.create_user(
            first_name=first_name,
            last_name=last_name,
            password_hash=self.hash_password(password),
            role=User.ROLE_USER,
        )

    def change_password(self, user_id: int, new_password: str) -> None:
        """Change a patient account password."""
        valid, message = validate_password(new_password)
        if not valid:
            raise ValueError(message)
        self.database_manager.update_user_password(
            user_id,
            self.hash_password(new_password),
        )
