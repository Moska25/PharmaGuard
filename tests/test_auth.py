"""
Authentication tests.

The migration path matters most here: this app previously stored unsalted
SHA-256 digests, and real deployments still hold them. Those logins must keep
working and must quietly upgrade, or patients get locked out of their reminders.
"""

import hashlib

import pytest

from auth_manager import (
    DEMO_ADMIN_PASSWORD,
    DEMO_ADMIN_USERNAME,
    PBKDF2_ITERATIONS,
    AuthManager,
    generate_temporary_password,
    validate_password,
)


class TestPasswordHashing:
    def test_hash_uses_pbkdf2_with_current_parameters(self):
        stored = AuthManager.hash_password("Correct!123")
        algorithm, iterations, salt, digest = stored.split("$")
        assert algorithm == "pbkdf2_sha256"
        assert int(iterations) == PBKDF2_ITERATIONS
        assert len(bytes.fromhex(salt)) == 16
        assert len(bytes.fromhex(digest)) == 32

    def test_correct_password_verifies(self):
        assert AuthManager.verify_password("Correct!123", AuthManager.hash_password("Correct!123"))

    def test_wrong_password_rejected(self):
        assert not AuthManager.verify_password("Wrong!123", AuthManager.hash_password("Correct!123"))

    def test_same_password_hashes_differently(self):
        """A per-user salt is the whole point: identical passwords must not collide.

        The leaked production database had two identical digests, which revealed
        that two accounts shared a password. Salting removes that signal.
        """
        first = AuthManager.hash_password("Correct!123")
        second = AuthManager.hash_password("Correct!123")
        assert first != second
        assert AuthManager.verify_password("Correct!123", first)
        assert AuthManager.verify_password("Correct!123", second)

    @pytest.mark.parametrize("bad", ["", "garbage", "pbkdf2_sha256$notanint$aa$bb", "a$b$c$d", "$$$"])
    def test_malformed_hash_returns_false_instead_of_raising(self, bad):
        assert AuthManager.verify_password("anything", bad) is False

    def test_unicode_password_round_trips(self):
        assert AuthManager.verify_password("პაროლი!23Aa", AuthManager.hash_password("პაროლი!23Aa"))


class TestLegacyHashes:
    def test_legacy_sha256_still_verifies(self):
        legacy = hashlib.sha256(b"Legacy!123").hexdigest()
        assert AuthManager.verify_password("Legacy!123", legacy)
        assert not AuthManager.verify_password("Nope!123", legacy)

    def test_legacy_hash_is_flagged_for_rehash(self):
        assert AuthManager.needs_rehash(hashlib.sha256(b"Legacy!123").hexdigest())

    def test_current_hash_is_not_flagged(self):
        assert not AuthManager.needs_rehash(AuthManager.hash_password("Correct!123"))

    def test_weaker_iteration_count_is_flagged(self):
        weak = AuthManager.hash_password("Correct!123").replace(
            f"${PBKDF2_ITERATIONS}$", "$1000$"
        )
        assert AuthManager.needs_rehash(weak)

    def test_login_transparently_upgrades_a_legacy_hash(self, database, auth):
        legacy = hashlib.sha256(b"Legacy!123").hexdigest()
        user = database.create_user("Old", "Account", legacy)

        assert auth.login_user(user.username, "Legacy!123") is not None

        stored = database.get_user_by_username(user.username).password
        assert stored.startswith("pbkdf2_sha256$")
        assert AuthManager.verify_password("Legacy!123", stored)
        # And the upgraded credential still works on the next login.
        assert auth.login_user(user.username, "Legacy!123") is not None

    def test_failed_login_does_not_upgrade(self, database, auth):
        legacy = hashlib.sha256(b"Legacy!123").hexdigest()
        user = database.create_user("Old", "Account", legacy)
        assert auth.login_user(user.username, "WrongGuess!1") is None
        assert database.get_user_by_username(user.username).password == legacy


class TestLogin:
    def test_patient_login_succeeds(self, auth, patient):
        assert auth.login_user(patient.username, "Correct!123") is not None

    def test_unknown_username_returns_none(self, auth):
        assert auth.login_user("nobody0001", "Correct!123") is None

    def test_deactivated_account_is_refused_with_a_message(self, database, auth, patient):
        database.update_user_active_status(patient.user_id, False)
        assert auth.login_user(patient.username, "Correct!123") is None
        assert auth.last_login_error == AuthManager.INACTIVE_MESSAGE

    def test_error_message_is_cleared_between_attempts(self, database, auth, patient):
        database.update_user_active_status(patient.user_id, False)
        auth.login_user(patient.username, "Correct!123")
        assert auth.last_login_error
        database.update_user_active_status(patient.user_id, True)
        auth.login_user(patient.username, "Correct!123")
        assert auth.last_login_error == ""


class TestAdminCredentials:
    def test_demo_admin_is_active_when_env_unset(self, database, monkeypatch):
        monkeypatch.delenv("PHARMAGUARD_ADMIN_PASSWORD", raising=False)
        manager = AuthManager(database)
        assert manager.using_demo_admin
        assert manager.login_admin(DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD) is not None

    def test_previously_leaked_password_no_longer_works(self, database, monkeypatch):
        monkeypatch.delenv("PHARMAGUARD_ADMIN_PASSWORD", raising=False)
        manager = AuthManager(database)
        assert manager.login_admin("Admin1", "Pharmguard1") is None

    def test_environment_overrides_the_demo_credentials(self, database, monkeypatch):
        monkeypatch.setenv("PHARMAGUARD_ADMIN_USER", "chief")
        monkeypatch.setenv("PHARMAGUARD_ADMIN_PASSWORD", "S3cure!Ops")
        manager = AuthManager(database)
        assert not manager.using_demo_admin
        assert manager.login_admin("chief", "S3cure!Ops") is not None
        assert manager.login_admin(DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD) is None

    def test_admin_role_is_set_on_the_returned_user(self, database, monkeypatch):
        monkeypatch.delenv("PHARMAGUARD_ADMIN_PASSWORD", raising=False)
        admin = AuthManager(database).login_admin(DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD)
        assert admin.role == "admin"


class TestPasswordPolicy:
    @pytest.mark.parametrize("good", ["Correct!123", "aB3$efgh", "პაროლი!23Aa"])
    def test_accepts_compliant_passwords(self, good):
        assert validate_password(good)[0]

    @pytest.mark.parametrize(
        "bad,expected",
        [
            ("Aa1!", "Minimum 8 characters"),
            ("lowercase1!", "uppercase"),
            ("UPPERCASE1!", "lowercase"),
            ("NoDigits!!", "number"),
            ("NoSpecial123", "special character"),
        ],
    )
    def test_rejects_and_explains(self, bad, expected):
        valid, message = validate_password(bad)
        assert not valid
        assert expected in message

    def test_account_creation_refuses_a_weak_password(self, auth):
        with pytest.raises(ValueError):
            auth.create_patient_user("Weak", "Password", "abc")

    def test_change_password_refuses_a_weak_password(self, auth, patient):
        with pytest.raises(ValueError):
            auth.change_password(patient.user_id, "abc")

    def test_change_password_updates_the_stored_hash(self, database, auth, patient):
        auth.change_password(patient.user_id, "Brand!New9")
        assert auth.login_user(patient.username, "Brand!New9") is not None
        assert auth.login_user(patient.username, "Correct!123") is None


class TestTemporaryPasswords:
    """Admin-initiated resets must not hand out one shared, guessable password."""

    def test_generated_password_satisfies_the_policy(self):
        for _ in range(50):
            assert validate_password(generate_temporary_password())[0]

    def test_generated_passwords_are_unique(self):
        assert len({generate_temporary_password() for _ in range(50)}) == 50

    def test_generated_password_can_be_used_to_log_in(self, auth, database, patient):
        temporary = generate_temporary_password()
        auth.change_password(patient.user_id, temporary)
        assert auth.login_user(patient.username, temporary) is not None
