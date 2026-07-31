"""
User model for PharmaGuard.

Users are patient accounts stored in SQLite.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Represents one PharmaGuard user or patient profile."""

    first_name: str
    last_name: str
    username: str
    password: str
    role: str = "user"
    user_id: Optional[int] = None
    created_at: str = ""
    is_active: int = 1

    ROLE_ADMIN = "admin"
    ROLE_USER = "user"

    @classmethod
    def from_row(cls, row) -> "User":
        """Create a User object from a sqlite3.Row."""
        return cls(
            user_id=row["id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            username=row["username"],
            password=row["password"],
            role=row["role"],
            created_at=row["created_at"] or "",
            is_active=int(row["is_active"] if "is_active" in row.keys() else 1),
        )

    @property
    def full_name(self) -> str:
        """Return first and last name together for display."""
        return f"{self.first_name} {self.last_name}".strip()

    def display_name(self) -> str:
        """Return display text used by patient dropdowns."""
        return f"{self.full_name} ({self.username})"

    def status_text(self) -> str:
        """Return account status for tables."""
        return "Active" if self.is_active else "Inactive"
