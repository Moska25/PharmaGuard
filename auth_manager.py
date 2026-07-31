"""
Authentication helper for PharmaGuard.

Patient passwords are stored as SHA-256 hashes.
"""

import hashlib
import string
from typing import Optional

from database import DatabaseManager
from user import User


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


class AuthManager:
    """Handles admin and patient authentication."""

    ADMIN_USERNAME = "Admin1"
    ADMIN_PASSWORD = "Pharmguard1"
    INACTIVE_MESSAGE = "Your account has been deactivated. Please contact the administrator."

    def __init__(self, database_manager: DatabaseManager) -> None:
        self.database_manager = database_manager
        self.last_login_error = ""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @classmethod
    def verify_password(cls, password: str, password_hash: str) -> bool:
        """Return True when password matches the stored hash."""
        return cls.hash_password(password) == password_hash

    def login_admin(self, username: str, password: str) -> Optional[User]:
        """Validate admin credentials."""
        self.last_login_error = ""
        if username == self.ADMIN_USERNAME and password == self.ADMIN_PASSWORD:
            return User(
                user_id=None,
                first_name="Admin",
                last_name="",
                username=self.ADMIN_USERNAME,
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
            return user
        return None

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
