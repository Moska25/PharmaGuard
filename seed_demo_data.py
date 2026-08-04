"""
Populate a PharmaGuard database with synthetic demo data.

The repository deliberately ships no database. Real patient records and password
hashes must never be committed, so reviewers generate their own local copy:

    python seed_demo_data.py

Every name, diagnosis, and medication below is invented. Re-running the script
is safe: it refuses to touch a database that already has patients unless you
pass --reset.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from auth_manager import AuthManager
from database import DatabaseManager
from medication import Medication

DEMO_PASSWORD = "Demo!Pass1"

# Fictional patients. Any resemblance to real people is coincidental.
DEMO_PATIENTS = [
    ("Ana", "Beridze", "Type 2 diabetes", "Penicillin", "Hypertension, Type 2 diabetes"),
    ("Luka", "Tsiklauri", "Post-operative recovery", "None known", "Asthma"),
    ("Mariam", "Kapanadze", "Iron deficiency anaemia", "Sulfa drugs", "Coeliac disease"),
    ("Davit", "Gogoladze", "Atrial fibrillation", "Aspirin", "Coronary artery disease"),
    ("Nino", "Abashidze", "Migraine with aura", "Latex", "Chronic migraine"),
]

# (medicine, dosage, time, rule, category, warning)
DEMO_MEDICATIONS = [
    ("Metformin", "500 mg", "08:00", "After food", "Antidiabetic", "May cause stomach upset"),
    ("Lisinopril", "10 mg", "09:00", "Before food", "Antihypertensive", "Monitor blood pressure"),
    ("Atorvastatin", "20 mg", "21:00", "After food", "Statin", "Avoid grapefruit juice"),
    ("Ferrous sulfate", "325 mg", "13:00", "With food", "Supplement", "Take with vitamin C"),
    ("Salbutamol", "100 mcg", "07:30", "As needed", "Bronchodilator", "Do not exceed 8 puffs daily"),
    ("Warfarin", "5 mg", "18:00", "Same time daily", "Anticoagulant", "Regular INR checks required"),
    ("Sumatriptan", "50 mg", "10:00", "At onset", "Antimigraine", "Maximum 2 doses in 24 hours"),
    ("Omeprazole", "20 mg", "07:00", "Before food", "PPI", "Take 30 minutes before breakfast"),
]


def seed(database_manager: DatabaseManager, *, days_back: int = 21, seed_value: int = 20260804) -> dict:
    """Insert demo patients, history, and medications. Returns a small summary."""
    # Deterministic so screenshots and test runs stay reproducible.
    generator = random.Random(seed_value)
    auth_manager = AuthManager(database_manager)
    password_hash = auth_manager.hash_password(DEMO_PASSWORD)

    created_users = []
    for first, last, diagnosis, allergies, chronic in DEMO_PATIENTS:
        user = database_manager.create_user(
            first_name=first,
            last_name=last,
            password_hash=password_hash,
            role="user",
        )
        created_users.append(user)
        database_manager.add_medical_history(
            user.user_id,
            {
                "diagnosis": diagnosis,
                "condition_notes": "Stable, reviewed at last appointment.",
                "allergies": allergies,
                "chronic_diseases": chronic,
                "past_surgeries": "None recorded",
                "current_symptoms": "None reported",
                "doctor_notes": "Continue current regimen. Review in 3 months.",
            },
        )

    today = date.today()
    medication_count = 0
    for user in created_users:
        # Two to three medicines per patient, repeated daily across the window.
        regimen = generator.sample(DEMO_MEDICATIONS, generator.randint(2, 3))
        for offset in range(-days_back, 3):
            day = today + timedelta(days=offset)
            for medicine, dosage, time_text, rule, category, warning in regimen:
                if offset < 0:
                    # Historic adherence around 85%, so the charts show a real pattern.
                    status = Medication.TAKEN if generator.random() < 0.85 else Medication.NOT_TAKEN
                elif offset == 0:
                    scheduled = datetime.strptime(f"{day} {time_text}", "%Y-%m-%d %H:%M")
                    status = Medication.TAKEN if scheduled < datetime.now() else Medication.NOT_TAKEN
                else:
                    status = Medication.NOT_TAKEN

                database_manager.add_medication(
                    Medication(
                        patient_name=user.full_name,
                        patient_id=user.user_id,
                        medicine_name=medicine,
                        dosage=dosage,
                        medication_date=day.isoformat(),
                        medicine_time=time_text,
                        taking_rule=rule,
                        status=status,
                        category=category,
                        warning=warning,
                    )
                )
                medication_count += 1

    database_manager.add_audit_log(
        "Demo data seeded",
        f"{len(created_users)} patients, {medication_count} medication records",
        actor_username="seed_demo_data",
        actor_role="admin",
    )
    return {"patients": len(created_users), "medications": medication_count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="Path to the SQLite file (default: pharma_guard.db)")
    parser.add_argument("--reset", action="store_true", help="Delete the existing database first")
    parser.add_argument("--days-back", type=int, default=21, help="Days of history to generate")
    arguments = parser.parse_args()

    db_path = Path(arguments.db) if arguments.db else Path(__file__).resolve().parent / "pharma_guard.db"
    if arguments.reset and db_path.exists():
        db_path.unlink()
        print(f"Removed {db_path}")

    database_manager = DatabaseManager(str(db_path))
    if database_manager.list_users():
        print(f"{db_path} already contains patients. Use --reset to rebuild it.")
        return 1

    summary = seed(database_manager)
    print(f"Seeded {summary['patients']} patients and {summary['medications']} medication records.")
    print(f"Database: {db_path}")
    print(f"Patient logins: <generated username> / {DEMO_PASSWORD}")
    for user in database_manager.list_users():
        print(f"  {user.full_name:<22} {user.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
