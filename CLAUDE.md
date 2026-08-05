# PharmaGuard

A **desktop** medication reminder and adherence-tracking application for a small clinic
or care setting. One administrator manages patient accounts, prescriptions and medical
history; each patient signs in and sees only their own schedule. A background scheduler
raises reminders ten minutes before a dose, at the dose time, and again once a dose is
missed.

Python 3.12 · PyQt5 · stdlib `sqlite3` · APScheduler · matplotlib.
Task ledger: **[TODO.md](TODO.md)**. House rules: `../MOSKA_MAIN/CLAUDE.md`.

---

## READ THIS FIRST: the leaked database is still in git history

`pharma_guard.db` is correctly `.gitignore`d and untracked in `HEAD`. **That does not
remove it.** The blob is still reachable in the pushed history at commit `002e9ab` on
`github.com/Moska25/PharmaGuard`, and anyone can fetch it. It contains:

- a `users` table of **10 real rows** — `first_name`, `last_name`, `username`, `password`
  (unsalted SHA-256; two digests are identical, so two people shared a password)
- a `medications` table carrying real `patient_name` values

Every password in that file must be treated as compromised regardless of what happens next.

**Do not attempt to fix this.** Purging history is destructive, it is Sandro's decision,
and it is tracked as `PHG-0.1` in [TODO.md](TODO.md) assigned to him. Agents working in
this repo must **never** run `git filter-repo`, `git rebase`, `git push`, `git commit`,
or any other git command. Leave the tree dirty.

---

## Desktop-only. Do not propose a web port.

PyQt5 is a native GUI toolkit. This app cannot be hosted, and rewriting it for the web
would be a different project, not a deployment. Its presentation to a recruiter is:

- captioned screenshots in `docs/screenshots/`
- a short demo GIF of one complete workflow
- a downloadable build attached to a GitHub release

That is the whole hosting conversation. It is settled.

---

## Running it

The venv already exists at `.venv/` with every dependency installed. System `python3` is
a 3.15 alpha with no Qt wheels — never use it.

```bash
.venv/bin/python seed_demo_data.py --reset     # 5 synthetic patients, 288 medication records
.venv/bin/python main.py                       # log in as Admin1 / PharmaGuard!Demo1
```

Rebuilding the venv from scratch:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Tests, screenshots — both run headless, no display server needed:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/capture_screenshots.py            # light
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/capture_screenshots.py --theme dark
```

### Seeding demo data

`seed_demo_data.py` is the reason the repo ships no database. It writes five invented
patients with Georgian names, one medical-history record each, and 21 days of back-dated
doses at roughly 85% historic adherence so the charts show a real pattern rather than a
flat line. It is deterministic (`seed_value=20260804`), so screenshots reproduce exactly.
It refuses to touch a database that already has patients unless you pass `--reset`.

`main.py` has no `--db` flag; it always opens `pharma_guard.db` next to the source. Tests
and the screenshot tool pass an explicit path to `DatabaseManager(...)` and use throwaway
files, so they never touch your local database.

## Demo credentials — the convention, and why it is fine

Two labelled fallbacks exist. Both are acceptable and should stay:

| Constant | Where | Behaviour |
| --- | --- | --- |
| `DEMO_ADMIN_PASSWORD` | `auth_manager.py` | Used only when `PHARMAGUARD_ADMIN_PASSWORD` is unset. `AuthManager.using_demo_admin` goes true and the login screen prints the credentials plus how to disable the notice. |
| `DEMO_PASSWORD` | `seed_demo_data.py` | The password given to every generated synthetic patient. Printed by the seeder. |

```bash
export PHARMAGUARD_ADMIN_USER=youradmin
export PHARMAGUARD_ADMIN_PASSWORD='choose-a-strong-one'
```

This satisfies non-negotiable #1 — no credential is hardcoded as *the* credential; the
environment always wins, the fallback is visibly labelled in the UI, and the accounts it
opens contain nothing but synthetic data. **Never** add a hardcoded password that is not
overridable and not surfaced on screen. That is the exact mistake this repo already made.

---

## Module map

`main.py` owns the application lifecycle: build `DatabaseManager` and `AuthManager`, apply
the saved theme, show `LoginDialog`, then construct a role-specific `MainWindow`. Logout
tears the window down and returns to the login dialog rather than exiting.

**Core — no Qt imports except `scheduler.py`'s signal**

| Module | Responsibility |
| --- | --- |
| `database.py` | The **only** module that touches SQLite. Owns the five tables, forward-only idempotent migrations, all CRUD, search, copy-day, statistics and the audit log. Everything else asks it. |
| `auth_manager.py` | PBKDF2-HMAC-SHA256 (240k iterations, per-user salt), password policy, admin/patient login, transparent re-hash of legacy unsalted SHA-256 on next successful login, temporary-password generation. |
| `medication.py` | The `Medication` dataclass plus the date arithmetic every screen depends on: `scheduled_datetime`, `normalized_medicine_time`, `is_overdue`, `minutes_until`, `minutes_late`, and the seven sort orders. |
| `user.py` | The `User` record and display helpers. |
| `scheduler.py` | APScheduler job, one tick a minute. Asks `database.py` for not-taken doses dated today or earlier, matches each against three time windows, writes the notification flag **before** emitting `reminder_due` so a crash mid-notification cannot double-fire. |
| `notification_manager.py` | Desktop notifications via `plyer` and audio cues via `QSoundEffect`, both wrapped in try/except so a missing backend degrades to an in-app popup instead of crashing. |

**Views — Qt widgets, thin, they call into the core**

| Module | Responsibility |
| --- | --- |
| `ui.py` | `MainWindow`. Tab container, the calendar/daily working surface, medication add/edit/delete/copy-day handlers, reminder popups, and `log_action` — the audit hook passed down to the other tabs. Largest file in the repo (1,095 lines). |
| `login_dialog.py` | `LoginDialog` and `CreateUserDialog`. Writes the login success/failure/user-created audit entries itself. |
| `dashboard.py` | Summary cards. Admin sees clinic-wide totals, missed list, upcoming list and a per-patient medical summary; a patient sees only their own. |
| `dialogs.py` | Add and edit medication dialogs, with category/warning autofill from `medicine_info.csv`. |
| `patient_widgets.py` | The searchable single-patient picker and the multi-select picker the statistics tab uses. |
| `statistics_window.py` | matplotlib charts over day / week / month / year / custom ranges, filtered by patient. |
| `user_profile.py` | Profile, password change, admin password reset, account activate/deactivate, and the medical-history CRUD. |
| `settings_tab.py` | Theme, notification and sound preferences, plus the admin-only audit-log viewer with search, role/date filters and CSV export. |
| `styles.py` | `LIGHT_STYLE` / `DARK_STYLE` Qt stylesheets and `set_app_theme`. |

**Tools** — `tools/capture_screenshots.py` (headless captures against a throwaway seeded
database), `tools/build_icons.py`, `tools/build_sounds.py` (stdlib `wave`, no dependency).

### How a reminder flows

```
APScheduler tick (1/min, background thread)
  └─ scheduler.check_medication_times(now)
       └─ database.get_pending_medications_for_scheduler(today)   -> not-taken, date <= today
            for each dose, match now against three windows:
              [t-10min, t)          -> EVENT_TEN_MINUTES
              [t, t+MISSED_GRACE)   -> EVENT_EXACT_TIME
              >= t+MISSED_GRACE     -> EVENT_MISSED
            └─ database.mark_notification_sent(id, flag)   <- persisted FIRST
               └─ emit reminder_due  ──[Qt queues to main thread]──> ui.handle_reminder_event
                                                                       ├─ popup
                                                                       └─ notification_manager cue
```

The flags live on the `medications` row, so a restart never re-fires an old reminder.
Editing a dose, or flipping it back to Not Taken, resets all three flags and re-arms it.

### Schema

`users`, `medications`, `patient_medical_history`, `settings`, `audit_log`. Migrations run
on every startup, are idempotent, check `PRAGMA table_info` and add only what is missing.
One legacy column (`medication_time`) needs a full table rebuild, done inside a transaction
in `_rebuild_without_legacy_medication_time`.

---

## Traps a fresh agent will hit

- **`MISSED_GRACE` is 1 minute.** A dose is declared missed 60 seconds after its scheduled
  time, so a patient gets the "take this now" popup and the "you missed it" popup a minute
  apart. `tests/test_scheduler.py` pins this, so changing it means changing tests. Tracked
  as `PHG-1.3`.
- **One malformed `medicine_time` aborts the whole scheduler pass.** `scheduled_datetime()`
  raises `ValueError` on anything `strptime` cannot read, nothing catches it, and under
  APScheduler the job just logs — every dose after the bad row silently never fires.
  Tracked as `PHG-1.1`.
- **`hmac.compare_digest` on `str` raises on non-ASCII.** `login_admin` compares the typed
  username this way, so a Georgian username on the admin tab is an unhandled exception in a
  Qt slot, which PyQt5 turns into `qFatal` — the app dies. Tracked as `PHG-1.2`.
- **The view layer has zero tests.** All 112 tests cover `auth_manager`, `database`,
  `medication` and `scheduler`. `ui.py`, `dashboard.py`, `statistics_window.py`,
  `user_profile.py`, `settings_tab.py` are unverified — roughly 3,000 lines.
- **`add_audit_log` swallows every exception and prints.** An append-only audit trail that
  can fail silently is not an audit trail. Tracked as `PHG-1.4`.
- **`"Segoe UI"` is hardcoded** in `styles.py` and does not exist on macOS; Qt logs a font
  warning on every run.
- **Never add a `.db`, `.sqlite` or `.sqlite3` file to the tree.** Extend the seeder.
- Deliberate shortcuts carry a `# ponytail:` comment naming the ceiling and the upgrade path.
- **All colour lives in `styles.py`.** Both themes generate from one template and two token
  dicts, so a rule cannot exist in one theme only, and `tests/test_styles.py` pins every
  contrast ratio against WCAG AA. Never hardcode a colour anywhere else; the check is
  `grep -rn '"#[0-9A-Fa-f]\{6\}"' --include="*.py" . | grep -v styles.py`, and it must
  stay empty.

## Working agreement

- The task ledger is **[TODO.md](TODO.md)** — stable ids `PHG-<phase>.<n>`, each task naming
  the files it touches and the condition that proves it is done. Tasks are written to be
  handed to a fresh agent with no context from the conversation that created them.
- The README must never promise what the tree does not contain. Anything not running goes
  under Roadmap or gets deleted.
- Nothing is "done" without proof: the app launched, the change screenshotted, real pytest
  output pasted, no console errors. "It should work now" is not done.
- **Never run a git command.** Sandro commits and publishes.
