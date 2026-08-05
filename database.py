"""
SQLite database manager for PharmaGuard.

The DatabaseManager class owns table creation, migration, CRUD operations,
daily queries, search, copy-day behavior, and notification flag updates.
"""

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set

from medication import Medication
from user import User


class DatabaseManager:
    """Handles all SQLite operations for medication reminder records."""

    NOTIFICATION_FLAGS = {
        "notified_10min_before",
        "notified_exact_time",
        "missed_notification_sent",
    }

    def __init__(self, db_path: Optional[str] = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.db_path = Path(db_path) if db_path else base_dir / "pharma_guard.db"
        self.create_users_table()
        self.migrate_users_table()
        self.create_table()
        self.migrate_table()
        self.create_medical_history_table()
        self.create_settings_table()
        self.create_audit_log_table()

    def create_users_table(self) -> None:
        """Create the users table for patient accounts."""
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def migrate_users_table(self) -> None:
        """Update the users table without removing existing accounts."""
        with self._connection() as connection:
            columns = self._table_columns(connection, "users")
            if "is_active" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
                )
            connection.execute(
                "UPDATE users SET is_active = 1 WHERE is_active IS NULL"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with column-name row access."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open and always close a SQLite connection."""
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def create_table(self) -> None:
        """Create the medications table for a new installation."""
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS medications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT NOT NULL,
                    patient_id INTEGER,
                    medicine_name TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    medication_date TEXT NOT NULL,
                    medicine_time TEXT NOT NULL,
                    taking_rule TEXT NOT NULL,
                    priority TEXT NOT NULL DEFAULT 'Normal',
                    status TEXT NOT NULL DEFAULT 'Not Taken',
                    category TEXT DEFAULT '',
                    warning TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    notified_10min_before INTEGER NOT NULL DEFAULT 0,
                    notified_exact_time INTEGER NOT NULL DEFAULT 0,
                    missed_notification_sent INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(patient_id) REFERENCES users(id)
                )
                """
            )
            connection.commit()

    def create_medical_history_table(self) -> None:
        """Create patient diagnosis/history storage without touching old data."""
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS patient_medical_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    diagnosis TEXT NOT NULL,
                    condition_notes TEXT,
                    allergies TEXT,
                    chronic_diseases TEXT,
                    past_surgeries TEXT,
                    current_symptoms TEXT,
                    doctor_notes TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(patient_id) REFERENCES users(id)
                )
                """
            )
            connection.commit()

    def create_settings_table(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            defaults = {
                "theme": "Light Theme",
                "notification_sounds": "On",
                "windows_notifications": "On",
                "notification_volume": "85",
                "daily_row_limit": "20",
                "auto_logout_minutes": "Off",
            }
            for key, value in defaults.items():
                connection.execute(
                    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                    (key, value),
                )
            connection.commit()

    def create_audit_log_table(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_user_id INTEGER,
                    actor_username TEXT,
                    actor_role TEXT,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

    def migrate_table(self) -> None:
        """Update the database schema without removing existing records."""
        with self._connection() as connection:
            columns = self._table_columns(connection)

            if "medication_date" not in columns:
                connection.execute(
                    "ALTER TABLE medications ADD COLUMN medication_date TEXT NOT NULL DEFAULT ''"
                )
                connection.execute(
                    "UPDATE medications SET medication_date = ? WHERE medication_date = ''",
                    (date.today().isoformat(),),
                )

            if "medicine_time" not in columns:
                connection.execute(
                    "ALTER TABLE medications ADD COLUMN medicine_time TEXT NOT NULL DEFAULT '00:00'"
                )
                if "medication_time" in columns:
                    connection.execute(
                        """
                        UPDATE medications
                        SET medicine_time = medication_time
                        WHERE medicine_time = '00:00' OR medicine_time = ''
                        """
                    )

            columns = self._table_columns(connection)
            if "medication_time" in columns and "medicine_time" in columns:
                connection.execute(
                    """
                    UPDATE medications
                    SET medicine_time = medication_time
                    WHERE (medicine_time IS NULL OR medicine_time = '' OR medicine_time = '00:00')
                      AND medication_time IS NOT NULL
                      AND medication_time != ''
                    """
                )

            optional_columns = {
                "patient_id": "INTEGER",
                "category": "TEXT DEFAULT ''",
                "warning": "TEXT DEFAULT ''",
                "created_at": "TEXT DEFAULT ''",
                "notified_10min_before": "INTEGER NOT NULL DEFAULT 0",
                "notified_exact_time": "INTEGER NOT NULL DEFAULT 0",
                "missed_notification_sent": "INTEGER NOT NULL DEFAULT 0",
            }

            columns = self._table_columns(connection)
            for column_name, column_type in optional_columns.items():
                if column_name not in columns:
                    connection.execute(
                        f"ALTER TABLE medications ADD COLUMN {column_name} {column_type}"
                    )

            connection.execute(
                """
                UPDATE medications
                SET created_at = CURRENT_TIMESTAMP
                WHERE created_at IS NULL OR created_at = ''
                """
            )

            columns = self._table_columns(connection)
            if "medication_time" in columns:
                self._rebuild_without_legacy_medication_time(connection)

            connection.commit()

    def _table_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str = "medications",
    ) -> Set[str]:
        """Return column names for a known application table."""
        if table_name not in {"medications", "users", "patient_medical_history", "settings", "audit_log"}:
            raise ValueError("Unknown table name.")
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}

    def _rebuild_without_legacy_medication_time(self, connection: sqlite3.Connection) -> None:
        """Safely remove the old medication_time column while preserving data."""
        connection.execute(
            """
            CREATE TABLE medications_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_name TEXT NOT NULL,
                patient_id INTEGER,
                medicine_name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                medication_date TEXT NOT NULL,
                medicine_time TEXT NOT NULL,
                taking_rule TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'Normal',
                status TEXT NOT NULL DEFAULT 'Not Taken',
                category TEXT DEFAULT '',
                warning TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                notified_10min_before INTEGER NOT NULL DEFAULT 0,
                notified_exact_time INTEGER NOT NULL DEFAULT 0,
                missed_notification_sent INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(patient_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO medications_new (
                id,
                patient_name,
                patient_id,
                medicine_name,
                dosage,
                medication_date,
                medicine_time,
                taking_rule,
                priority,
                status,
                category,
                warning,
                created_at,
                notified_10min_before,
                notified_exact_time,
                missed_notification_sent
            )
            SELECT
                id,
                patient_name,
                patient_id,
                medicine_name,
                dosage,
                CASE
                    WHEN medication_date IS NOT NULL AND medication_date != '' THEN medication_date
                    ELSE DATE('now')
                END,
                CASE
                    WHEN medicine_time IS NOT NULL AND medicine_time != '' THEN medicine_time
                    WHEN medication_time IS NOT NULL AND medication_time != '' THEN medication_time
                    ELSE '00:00'
                END,
                taking_rule,
                priority,
                status,
                category,
                warning,
                CASE
                    WHEN created_at IS NOT NULL AND created_at != '' THEN created_at
                    ELSE CURRENT_TIMESTAMP
                END,
                notified_10min_before,
                notified_exact_time,
                missed_notification_sent
            FROM medications
            """
        )
        connection.execute("DROP TABLE medications")
        connection.execute("ALTER TABLE medications_new RENAME TO medications")

    def normalize_name_for_username(self, value: str) -> str:
        """Keep usernames simple and predictable."""
        return "".join(character.lower() for character in value if character.isalnum())

    def generate_username(self, first_name: str, last_name: str) -> str:
        """Generate firstname+lastname+four-digit-number username."""
        base = f"{self.normalize_name_for_username(first_name)}{self.normalize_name_for_username(last_name)}"
        if not base:
            base = "patient"

        with self._connection() as connection:
            number = 1
            while True:
                username = f"{base}{number:04d}"
                exists = connection.execute(
                    "SELECT 1 FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
                if not exists:
                    return username
                number += 1

    def create_user(self, first_name: str, last_name: str, password_hash: str, role: str = "user") -> User:
        """Create a new patient user with a generated unique username."""
        username = self.generate_username(first_name, last_name)
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (first_name, last_name, username, password, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (first_name.strip(), last_name.strip(), username, password_hash, role),
            )
            connection.commit()
            user_id = int(cursor.lastrowid)
        user = self.get_user_by_id(user_id)
        if user is None:
            raise RuntimeError("Created user could not be loaded.")
        return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Return one user by id."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return User.from_row(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Return one user by username."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        return User.from_row(row) if row else None

    def list_users(self, search_text: str = "", active_filter: Optional[str] = None) -> List[User]:
        """List patient users, optionally filtered by name or username."""
        search = search_text.strip()
        conditions = []
        values = []

        if search:
            conditions.append(
                """
                (first_name LIKE ?
                 OR last_name LIKE ?
                 OR first_name || ' ' || last_name LIKE ?
                 OR username LIKE ?)
                """
            )
            values.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])

        if active_filter == "active":
            conditions.append("is_active = 1")
        elif active_filter == "inactive":
            conditions.append("is_active = 0")

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id, first_name, last_name, username, password, role, is_active,
                    DATETIME(created_at, 'localtime') AS created_at
                FROM users
                {where_sql}
                ORDER BY first_name COLLATE NOCASE, last_name COLLATE NOCASE
                """,
                values,
            ).fetchall()
        return [User.from_row(row) for row in rows]

    def update_user_password(self, user_id: int, password_hash: str) -> None:
        """Update a user's stored password hash."""
        with self._connection() as connection:
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (password_hash, user_id),
            )
            connection.commit()

    def update_user_active_status(self, user_id: int, is_active: bool) -> None:
        """Activate or deactivate a user account."""
        with self._connection() as connection:
            connection.execute(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if is_active else 0, user_id),
            )
            connection.commit()

    def add_medical_history(self, patient_id: int, data: Dict[str, str]) -> int:
        """Add a diagnosis/history record for a patient."""
        diagnosis = data.get("diagnosis", "").strip()
        if not patient_id:
            raise ValueError("Patient must be selected.")
        if not diagnosis:
            raise ValueError("Diagnosis cannot be empty.")

        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO patient_medical_history (
                    patient_id,
                    diagnosis,
                    condition_notes,
                    allergies,
                    chronic_diseases,
                    past_surgeries,
                    current_symptoms,
                    doctor_notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    diagnosis,
                    data.get("condition_notes", "").strip(),
                    data.get("allergies", "").strip(),
                    data.get("chronic_diseases", "").strip(),
                    data.get("past_surgeries", "").strip(),
                    data.get("current_symptoms", "").strip(),
                    data.get("doctor_notes", "").strip(),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_medical_history(self, history_id: int, data: Dict[str, str]) -> None:
        """Update a diagnosis/history record."""
        diagnosis = data.get("diagnosis", "").strip()
        if not diagnosis:
            raise ValueError("Diagnosis cannot be empty.")

        with self._connection() as connection:
            connection.execute(
                """
                UPDATE patient_medical_history
                SET diagnosis = ?,
                    condition_notes = ?,
                    allergies = ?,
                    chronic_diseases = ?,
                    past_surgeries = ?,
                    current_symptoms = ?,
                    doctor_notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    diagnosis,
                    data.get("condition_notes", "").strip(),
                    data.get("allergies", "").strip(),
                    data.get("chronic_diseases", "").strip(),
                    data.get("past_surgeries", "").strip(),
                    data.get("current_symptoms", "").strip(),
                    data.get("doctor_notes", "").strip(),
                    history_id,
                ),
            )
            connection.commit()

    def delete_medical_history(self, history_id: int) -> None:
        """Delete one diagnosis/history record."""
        with self._connection() as connection:
            connection.execute("DELETE FROM patient_medical_history WHERE id = ?", (history_id,))
            connection.commit()

    def get_medical_history_by_patient(
        self,
        patient_id: Optional[int],
        search_text: str = "",
    ) -> List[Dict[str, str]]:
        """Load medical history records for one patient, or all patients for admin search."""
        conditions = []
        values = []

        if patient_id is not None:
            conditions.append("h.patient_id = ?")
            values.append(patient_id)

        search = search_text.strip()
        if search:
            conditions.append(
                """
                (u.first_name LIKE ?
                 OR u.last_name LIKE ?
                 OR u.first_name || ' ' || u.last_name LIKE ?
                 OR u.username LIKE ?
                 OR h.diagnosis LIKE ?
                 OR h.condition_notes LIKE ?
                 OR h.doctor_notes LIKE ?)
                """
            )
            values.extend([f"%{search}%"] * 7)

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    h.*,
                    DATETIME(h.created_at, 'localtime') AS created_at,
                    DATETIME(h.updated_at, 'localtime') AS updated_at,
                    u.first_name, u.last_name, u.username
                FROM patient_medical_history h
                JOIN users u ON u.id = h.patient_id
                {where_sql}
                ORDER BY h.updated_at DESC, h.created_at DESC
                """,
                values,
            ).fetchall()

        records = []
        for row in rows:
            record = dict(row)
            record["patient_name"] = f"{row['first_name']} {row['last_name']}".strip()
            record["patient_username"] = row["username"]
            records.append(record)
        return records

    def get_latest_medical_summary(self, patient_id: int) -> Dict[str, str]:
        """Return the newest diagnosis, allergies, and chronic diseases for a patient."""
        if not patient_id:
            return {}

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT diagnosis, allergies, chronic_diseases
                FROM patient_medical_history
                WHERE patient_id = ?
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """,
                (patient_id,),
            ).fetchall()

        if not rows:
            return {}

        summary = {"diagnosis": rows[0]["diagnosis"] or "", "allergies": "", "chronic_diseases": ""}
        for row in rows:
            if not summary["allergies"] and row["allergies"]:
                summary["allergies"] = row["allergies"]
            if not summary["chronic_diseases"] and row["chronic_diseases"]:
                summary["chronic_diseases"] = row["chronic_diseases"]
        return summary

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connection() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            connection.commit()

    def add_audit_log(
        self,
        action: str,
        details: str = "",
        actor_user_id: Optional[int] = None,
        actor_username: str = "",
        actor_role: str = "",
    ) -> None:
        try:
            with self._connection() as connection:
                connection.execute(
                    """
                    INSERT INTO audit_log (
                        actor_user_id, actor_username, actor_role, action, details
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (actor_user_id, actor_username, actor_role, action, details),
                )
                connection.commit()
        except Exception as error:
            print(f"Audit log warning: {error}")

    def get_audit_logs(
        self,
        search_text: str = "",
        role: str = "All",
        start_date: str = "",
        end_date: str = "",
    ) -> List[Dict[str, str]]:
        conditions = []
        values = []
        if role and role != "All":
            conditions.append("actor_role = ?")
            values.append(role.lower())
        # created_at is stored in UTC by CURRENT_TIMESTAMP, which is right for an
        # audit trail, but the dates arriving from the Settings tab's date pickers
        # are local. Comparing the two directly loses entries on any machine that
        # is not on UTC: west of UTC a late-evening action carries tomorrow's UTC
        # date and falls outside a filter ending on local today, and east of UTC
        # the early hours carry yesterday's and fall outside one starting today.
        # Either way the audit table rendered empty while rows existed. Convert at
        # the boundary, in SQL, and leave storage in UTC where it belongs.
        if start_date:
            conditions.append("DATE(created_at, 'localtime') >= ?")
            values.append(start_date)
        if end_date:
            conditions.append("DATE(created_at, 'localtime') <= ?")
            values.append(end_date)

        search = search_text.strip()
        if search:
            conditions.append("(actor_username LIKE ? OR action LIKE ? OR actor_role LIKE ? OR details LIKE ?)")
            values.extend([f"%{search}%"] * 4)

        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    actor_user_id,
                    actor_username,
                    actor_role,
                    action,
                    details,
                    DATETIME(created_at, 'localtime') AS created_at
                FROM audit_log
                {where_sql}
                ORDER BY created_at DESC
                LIMIT 500
                """,
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def add_medication(self, medication: Medication) -> int:
        """Insert a medication reminder and return its new id."""
        required_fields = {
            "patient_name": medication.patient_name,
            "medicine_name": medication.medicine_name,
            "dosage": medication.dosage,
            "medication_date": medication.medication_date,
            "medicine_time": medication.medicine_time,
        }
        missing_fields = [name for name, value in required_fields.items() if not str(value or "").strip()]
        if missing_fields:
            raise ValueError(f"Missing required medication fields: {', '.join(missing_fields)}")

        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO medications (
                    patient_name,
                    patient_id,
                    medicine_name,
                    dosage,
                    medication_date,
                    medicine_time,
                    taking_rule,
                    status,
                    category,
                    warning,
                    notified_10min_before,
                    notified_exact_time,
                    missed_notification_sent
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                medication.to_insert_tuple(),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def update_medication(self, medication: Medication) -> None:
        """Update editable medication fields and reset notification flags."""
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE medications
                SET
                    patient_name = ?,
                    patient_id = ?,
                    medicine_name = ?,
                    dosage = ?,
                    medication_date = ?,
                    medicine_time = ?,
                    taking_rule = ?,
                    status = ?,
                    category = ?,
                    warning = ?,
                    notified_10min_before = 0,
                    notified_exact_time = 0,
                    missed_notification_sent = 0
                WHERE id = ?
                """,
                medication.to_update_tuple(),
            )
            connection.commit()

    def delete_medication(self, medication_id: int) -> None:
        """Delete one medication reminder by id."""
        with self._connection() as connection:
            connection.execute("DELETE FROM medications WHERE id = ?", (medication_id,))
            connection.commit()

    def update_medication_status(self, medication_id: int, status: str) -> None:
        """Set a medication status to Taken or Not Taken."""
        with self._connection() as connection:
            if status == Medication.NOT_TAKEN:
                connection.execute(
                    """
                    UPDATE medications
                    SET status = ?,
                        notified_10min_before = 0,
                        notified_exact_time = 0,
                        missed_notification_sent = 0
                    WHERE id = ?
                    """,
                    (status, medication_id),
                )
            else:
                connection.execute(
                    "UPDATE medications SET status = ? WHERE id = ?",
                    (status, medication_id),
                )
            connection.commit()

    def mark_notification_sent(self, medication_id: int, flag_name: str) -> None:
        """Set one notification flag to 1 after a reminder is sent."""
        if flag_name not in self.NOTIFICATION_FLAGS:
            raise ValueError(f"Unknown notification flag: {flag_name}")

        with self._connection() as connection:
            connection.execute(
                f"UPDATE medications SET {flag_name} = 1 WHERE id = ?",
                (medication_id,),
            )
            connection.commit()

    def get_medication_by_id(self, medication_id: int) -> Optional[Medication]:
        """Return one medication by id, or None if it was not found."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM medications WHERE id = ?",
                (medication_id,),
            ).fetchone()
        return Medication.from_row(row) if row else None

    def _load_medications(
        self,
        conditions: Optional[List[str]] = None,
        values: Optional[List] = None,
        order_by: str = "medication_date ASC, medicine_time ASC, patient_name ASC",
    ) -> List[Medication]:
        where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM medications {where_sql} ORDER BY {order_by}",
                values or [],
            ).fetchall()
        return [Medication.from_row(row) for row in rows]

    def load_all_medications(self, patient_id: Optional[int] = None) -> List[Medication]:
        """Load all medication reminders ordered by date and time."""
        conditions = ["patient_id = ?"] if patient_id is not None else []
        values = [patient_id] if patient_id is not None else []
        return self._load_medications(conditions, values)

    def load_medications_by_date(self, medication_date: str, patient_id: Optional[int] = None) -> List[Medication]:
        """Load medications scheduled for one date."""
        conditions = ["medication_date = ?"]
        values = [medication_date]
        if patient_id is not None:
            conditions.append("patient_id = ?")
            values.append(patient_id)
        return self._load_medications(
            conditions,
            values,
            "medicine_time ASC, patient_name ASC, medicine_name ASC",
        )

    def load_medications_for_range(
        self,
        start_date: str = "",
        end_date: str = "",
        patient_name: str = "",
        patient_id: Optional[int] = None,
    ) -> List[Medication]:
        """Load medications using optional date-range and patient filters."""
        conditions = []
        values = []

        if start_date:
            conditions.append("medication_date >= ?")
            values.append(start_date)

        if end_date:
            conditions.append("medication_date <= ?")
            values.append(end_date)

        if patient_name:
            conditions.append("patient_name = ?")
            values.append(patient_name)

        if patient_id is not None:
            conditions.append("patient_id = ?")
            values.append(patient_id)

        return self._load_medications(conditions, values)

    def get_pending_medications_for_scheduler(self, today: str, patient_id: Optional[int] = None) -> List[Medication]:
        """Return not-taken records for today or earlier dates."""
        conditions = ["status = ?", "medication_date <= ?"]
        values = [Medication.NOT_TAKEN, today]
        if patient_id is not None:
            conditions.append("patient_id = ?")
            values.append(patient_id)
        return self._load_medications(
            conditions,
            values,
            "medication_date ASC, medicine_time ASC",
        )

    def get_dates_with_medications(self, patient_id: Optional[int] = None) -> Set[str]:
        """Return date strings that have at least one reminder."""
        with self._connection() as connection:
            if patient_id is None:
                rows = connection.execute(
                    "SELECT DISTINCT medication_date FROM medications"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT DISTINCT medication_date
                    FROM medications
                    WHERE patient_id = ?
                    """,
                    (patient_id,),
                ).fetchall()
        return {row["medication_date"] for row in rows}

    def copy_day(self, source_date: str, target_date: str, patient_id: Optional[int] = None) -> int:
        """
        Copy all reminders from source_date to target_date.

        Status and notification flags are reset so the copied records behave
        like fresh reminders.
        """
        source_medications = self.load_medications_by_date(source_date, patient_id)
        for medication in source_medications:
            self.add_medication(
                Medication(
                    patient_name=medication.patient_name,
                    patient_id=medication.patient_id,
                    medicine_name=medication.medicine_name,
                    dosage=medication.dosage,
                    medication_date=target_date,
                    medicine_time=medication.medicine_time,
                    taking_rule=medication.taking_rule,
                    status=Medication.NOT_TAKEN,
                    category=medication.category,
                    warning=medication.warning,
                )
            )
        return len(source_medications)

    def get_statistics_for_date(self, medication_date: str, patient_id: Optional[int] = None) -> Dict[str, int]:
        """Return daily totals for labels and matplotlib charts."""
        medications = self.load_medications_by_date(medication_date, patient_id)
        taken = sum(1 for item in medications if item.status == Medication.TAKEN)
        not_taken = sum(1 for item in medications if item.status == Medication.NOT_TAKEN)
        overdue = sum(1 for item in medications if item.is_overdue())

        return {
            "total": len(medications),
            "taken": taken,
            "not_taken": not_taken,
            "overdue": overdue,
        }
