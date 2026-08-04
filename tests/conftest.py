"""Shared fixtures. Every test gets its own throwaway SQLite file."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_manager import AuthManager  # noqa: E402
from database import DatabaseManager  # noqa: E402


@pytest.fixture
def database(tmp_path) -> DatabaseManager:
    """A fresh, empty database per test."""
    return DatabaseManager(str(tmp_path / "test.db"))


@pytest.fixture
def auth(database) -> AuthManager:
    return AuthManager(database)


@pytest.fixture
def patient(database):
    """One patient account with a known password."""
    return database.create_user("Ana", "Beridze", AuthManager.hash_password("Correct!123"))
