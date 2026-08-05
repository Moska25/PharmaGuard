# PharmaGuard — roadmap

## Status

The app runs. Verified 2026-08-04 on macOS: launched windowed on the `cocoa` platform,
all six tabs render, and stderr is empty on the real launch and on both screenshot runs.
**The suite is green: 153 tests, 0 failures** in 1.38s
(`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q`). `docs/screenshots/`
holds 22 captures: seven screens plus four dialogs, in both themes.

Landed so far: the first pass's security work (PBKDF2 replacing unsalted SHA-256, admin
credentials in the environment, the database untracked and replaced by a seeder); the
"Clinical Instrument" identity from `MOSKA_MAIN/shared/UI_IDENTITIES.md` across both
themes (Phase 4); the Statistics tab (Phase 5); the font chain (`PHG-6.1`); the audit
log's UTC/local mismatch (`PHG-1.6`); and the dialogs and secondary screens (Phase 8).

What is **not** true yet:

- The leaked database is still fetchable from pushed git history. `PHG-0.1`, and Sandro's
  decision alone.
- Four silent-failure paths remain open in Phase 1. Two of them take the app or the
  reminder engine down with no visible error: one unparseable `medicine_time` aborts the
  whole scheduler pass, and a non-ASCII admin username crashes the process.
- The view layer still has no direct tests. Roughly 3,000 lines across `ui.py`,
  `dashboard.py`, `statistics_window.py`, `user_profile.py` and `settings_tab.py` are
  exercised only by the screenshot tool constructing them.
- "Taken Today %" on the dashboard still divides by doses not yet due, and the README
  still calls it an adherence rate. `PHG-1.5`.

This app is the closest of the legacy repos to showable, so the roadmap stays weighted
toward **proof that the existing features work** rather than new features.

## How to pick up a task

1. Read `CLAUDE.md` in this repo and `../MOSKA_MAIN/CLAUDE.md` before writing any code.
2. Work only the task ids you were assigned. Do not do adjacent "while I'm here" work; if
   you find something worth doing, add it as a new id at the end of its phase.
3. Before reporting back: launch the app (`.venv/bin/python main.py`) and confirm the
   affected screen renders, then run
   `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/ -q` and confirm it is green.
   Update the `## Status` paragraph above with the new test count.
4. **Never run a git command.** No `add`, no `commit`, no `push`, no `filter-repo`, no
   branches. Leave the tree dirty; Sandro commits.
5. Mark finished tasks `- [x]` and leave them in place.
6. Report back: files touched, what you verified and how, test count and result, anything cut.

---

## Phase 0 — Sandro only. Do not assign this to an agent.

- [ ] **PHG-0.1** Decide how to purge `pharma_guard.db` from the pushed history of
      `github.com/Moska25/PharmaGuard`, where it is still fetchable at commit `002e9ab`
      containing 10 real names and unsalted SHA-256 password hashes (two identical, so two
      people shared a password) plus real `patient_name` values in `medications`.
      Files: none in this repo — this is a history rewrite, not a code change.
      Options: (1) delete the GitHub repo and re-push a clean single-commit history — no
      stars, forks or issues to lose, and the recommended route; (2)
      `git filter-repo --path pharma_guard.db --invert-paths` then force-push, which leaves
      the blob cached on GitHub until support purges it; (3) accept it, having rotated every
      password.
      A backup of the original is at `~/Downloads/pharma_guard.LEAKED-BACKUP.db`.
      Done when: fetching the blob from a fresh clone of the public repo returns nothing, and
      every person in that file has been told their password is compromised. Regardless of
      the option chosen, that notification is not optional.

---

## Phase 1 — Silent failures that matter clinically (1 of 6 done)

Found by the 2026-08-04 audit. Each of these fails without an error a user would see, which
is the worst failure mode for a medication app. All four are small diffs.

- [ ] **PHG-1.1** Guard `scheduler.check_medication_times` so one unparseable
      `medicine_time` cannot abort the whole pass. Today `medication.scheduled_datetime()`
      raises `ValueError` on anything `strptime` cannot read (`"morning"`, `""`, a bare
      `"8"`), nothing catches it, and under APScheduler the job only logs — so every dose
      ordered after the bad row silently never fires, for every patient. Skip the bad row,
      write one audit entry naming the medication id, continue the loop.
      Files: `scheduler.py`, `medication.py`, `tests/test_scheduler.py`
      Done when: a test inserts one row with `medicine_time="morning"` and one valid dose
      ordered after it, and asserts the valid dose still fires and an audit entry records
      the skip.
- [ ] **PHG-1.2** Stop `login_admin` crashing the application on a non-ASCII username.
      `hmac.compare_digest` raises `TypeError: comparing strings with non-ASCII characters
      is not supported` on `str` inputs; `AuthManager.login_admin` passes the typed username
      straight in, `LoginDialog.login` does not catch it, and an unhandled exception in a Qt
      slot makes PyQt5 call `qFatal` and abort. A Georgian username on the admin tab kills
      the app. Compare UTF-8 `bytes`, not `str`.
      Files: `auth_manager.py`, `tests/test_auth.py`
      Done when: `login_admin("ანა", "x")` returns `None` instead of raising, the correct
      demo credentials still authenticate, and a test covers both.
- [ ] **PHG-1.3** Make the missed-dose grace window configurable and set a clinically
      sensible default. `ReminderScheduler.MISSED_GRACE` is 1 minute, so the "take this now"
      popup and the "you missed it" popup arrive 60 seconds apart, and `Medication.is_overdue`
      returns true one second after the scheduled time — which is what drives the Dashboard
      "Missed Medications" count and the Statistics "Overdue" card. Read the window from the
      `settings` table (`missed_grace_minutes`), default 30, expose it in the Settings tab.
      Files: `scheduler.py`, `medication.py`, `database.py`, `settings_tab.py`,
      `tests/test_scheduler.py`, `tests/test_medication.py`
      Done when: with the default, a dose at 12:00 fires `EVENT_EXACT_TIME` at 12:00 and
      `EVENT_MISSED` at 12:30 and not before; the existing scheduler tests are updated rather
      than deleted; and `is_overdue` takes the same window so the three screens agree.
- [ ] **PHG-1.4** Stop `DatabaseManager.add_audit_log` swallowing failures into a `print`.
      An append-only audit trail that can fail invisibly is not an audit trail — in a care
      setting the record of who changed a prescription is the thing you cannot lose. Keep it
      non-fatal (a failed log must not lose the user's edit) but make it loud: re-raise on
      programmer error, and surface a persistent warning banner in the Settings tab when a
      write has failed this session.
      Files: `database.py`, `settings_tab.py`, `tests/test_database.py`
      Done when: a test forces an insert failure and asserts the failure is recorded and
      retrievable, not printed and discarded.
- [x] **PHG-1.6** Stop the audit log silently hiding entries across the UTC boundary.
      SQLite's `CURRENT_TIMESTAMP` writes **UTC**, and every date the UI compares it against
      is **local**. Anywhere off UTC that gap swallows entries: west of UTC an action taken
      at 21:00 local carries tomorrow's UTC date and drops out of a filter ending on local
      today, and east of UTC the early hours carry yesterday's and drop out of one starting
      today. Either way the Settings tab renders an empty audit table while rows exist.
      Reproduced on this machine (UTC-4) with a one-row probe -
      `end_date` local today returns 0, `end_date` UTC today returns 1. The same mismatch
      prints the users table's Created Date as tomorrow after 20:00, and skews
      `patient_medical_history` ordering.
      Keep storing UTC, which is right for an audit trail, and convert at the boundary with
      SQLite's `'localtime'` modifier rather than in Python.
      Files: `database.py`, `user_profile.py`, `tests/test_database.py`
      **Done.** Storage stays UTC; `DATE(created_at, 'localtime')` filters and
      `DATETIME(created_at, 'localtime')` displays, in `get_audit_logs`, `list_users` and
      `get_medical_history_by_patient`. Four tests added, and checked against the old SQL:
      three of them fail on it. The fixed-timestamp test derives its moment from the
      machine's own offset so it straddles the date boundary wherever it runs, and skips
      with a reason on a UTC machine rather than passing vacuously. The Settings audit
      table now renders rows in local time in the regenerated screenshot.
- [ ] **PHG-1.5** Fix or relabel "Taken Today %" on the admin dashboard. It divides today's
      taken doses by *all* of today's doses including ones not yet due
      (`dashboard.py:116`), so a clinic with perfect adherence reads 0% at 08:00 and climbs
      through the day. The README calls this the "adherence rate", which it is not. Either
      restrict the denominator to doses already due, or rename the card to "Day complete %"
      and add a true adherence figure beside it.
      Files: `dashboard.py`, `README.md`, `tests/test_dashboard.py` (new)
      Done when: the displayed number is computed by a function with a test, and the README
      calls it whatever the UI calls it. Non-negotiable #5 — no number the code does not
      actually compute the way its label claims.

## Phase 2 — Evidence a recruiter can see (not started)

The strategic priority. This app cannot be hosted, so these assets *are* the demo.

- [ ] **PHG-2.1** Rehearse the README quickstart from a genuinely clean clone and fix
      whatever breaks. Copy the tree to a temp directory excluding `.venv/`,
      `pharma_guard.db`, `__pycache__/` and `.pytest_cache/`, then run the README's commands
      verbatim on Python 3.12 with nothing cached.
      Files: `README.md`, `requirements.txt`
      Done when: the transcript of that run is pasted into the report, ends with a visible
      window, and the README's Quickstart matches it character for character.
- [ ] **PHG-2.2** Recapture `docs/screenshots/` after Phase 1 lands, both themes, and write
      a real caption per image. The existing captures predate the audit fixes.
      Files: `docs/screenshots/*.png`, `tools/capture_screenshots.py`, `README.md`
      Done when: every screenshot the README links resolves, shows only synthetic seeded
      data, and carries a caption that says what a reviewer should notice in it.
- [ ] **PHG-2.3** Record a demo GIF of one complete workflow: admin logs in, adds a
      medication for a patient, the ten-minute reminder popup fires, the patient marks it
      taken, the dashboard and statistics both update. Drive it from a script with an
      injected clock rather than waiting on the wall clock.
      Files: `tools/record_demo.py` (new), `docs/demo.gif`, `README.md`
      Done when: the GIF is under 5 MB, under 30 seconds, needs no audio or captions to
      follow, and is the first image in the README after the hero.
- [ ] **PHG-2.4** Reconcile every claim in `README.md` against the tree. The audit already
      found three that are wrong: "Every login, failure, and record change is written to an
      append-only audit log" (settings changes and logouts are logged, but the *scheduler*
      writes no audit entry at all when it fires or skips a reminder); "adherence rate" for
      a figure the UI honestly calls "Completion %" / "Taken Today %"; and the limitation
      "The audit log has no UI-driven retention or export yet" — CSV export exists at
      `settings_tab.export_audit_csv`, so that limitation is stale.
      Files: `README.md`
      Done when: each Features bullet has been traced to the function that implements it,
      and anything that could not be traced has moved to Roadmap or been deleted.
- [ ] **PHG-2.5** Document the one access-control decision a reviewer will ask about: the
      login screen's **Create User** button lets anyone create a patient account without
      authenticating, while the README opens with "One administrator manages patient
      accounts". Either gate it behind an admin session or state plainly in the README why
      self-registration is deliberate.
      Files: `login_dialog.py` and/or `README.md`
      Done when: the code and the README tell the same story about who can create an account.

## Phase 3 — Tests where a silent break would matter (not started)

The suite is strong on `auth_manager`, `database`, `medication` and `scheduler`, and absent
everywhere else. These are the specific gaps, ordered by what a silent break would cost.

- [ ] **PHG-3.1** Test the legacy-schema migration. `migrate_table` and
      `_rebuild_without_legacy_medication_time` drop and rebuild the `medications` table —
      the only code in the repo that can destroy a real installation's records — and nothing
      exercises it. `test_opening_an_existing_database_is_idempotent` only opens a fresh
      database twice, which never reaches the rebuild path.
      Files: `tests/test_migrations.py` (new)
      Done when: a test hand-builds a pre-migration database (with `medication_time`, without
      `patient_id` / `category` / `warning` / the three notification flags), opens it through
      `DatabaseManager`, and asserts every row survived with its time value carried across.
- [ ] **PHG-3.2** Test the audit-log query surface. `get_audit_logs` filters by role, date
      range and free text and silently caps at `LIMIT 500`; none of that is covered, and an
      audit search that quietly returns the wrong rows is a control failure, not a bug.
      Files: `tests/test_database.py`
      Done when: role, start-date, end-date and search filters each have a test, and the
      500-row cap either has a test proving the UI says it truncated or has been replaced by
      paging.
- [ ] **PHG-3.3** Test that each mutating action writes its audit entry. `ui.log_action` and
      `user_profile.log_action` are called at 14 sites; none is verified. Cover the ones with
      clinical weight by calling the handlers directly against a temp database.
      Files: `tests/test_audit.py` (new)
      Done when: medication added / edited / deleted / marked taken, day copied, password
      reset, and account deactivated each assert a matching `audit_log` row with the right
      actor and role.
- [ ] **PHG-3.4** Test the "Overdue first" sort order, the only one of the seven in
      `MEDICATION_SORT_OPTIONS` with no test — and the only one whose key function
      (`is_overdue()`) reads the wall clock, so it is both untested and non-deterministic.
      Files: `medication.py`, `tests/test_medication.py`
      Done when: `sort_medications` takes an optional reference time, threads it into
      `is_overdue`, and a test pins the order against a fixed clock.
- [ ] **PHG-3.5** Cover the DST boundary in the scheduler. Every datetime in the app is naive
      local time, so a spring-forward can skip a dose window and an autumn-back can present
      the same hour twice.
      Files: `tests/test_scheduler.py`, `scheduler.py`
      Done when: a test asserts what happens to a dose scheduled inside the transition, and
      whatever the answer is, `README.md` Known Limitations states it.

## Phase 4 — Visual identity: "Clinical Instrument" (done 2026-08-04)

Spec: `../MOSKA_MAIN/shared/UI_IDENTITIES.md`.

- [x] **PHG-4.1** Apply the token palette to both themes.
      Files: `styles.py`
      Both sheets are now generated from one template and two token dicts. Light previously
      carried 8 rules against dark's 380, so cards, titles and tabs fell back to stock Qt in
      light mode; a rule can no longer exist in one theme only. Every value was picked
      against a measured contrast ratio: the spec's `#0D9488` reaches only 3.74:1 under white
      button text, so `#0F766E` fills buttons (5.47:1) and `#0D9488` is kept for rules and
      focus rings where it carries no text; the spec's `#7C8BA1` muted reads 3.46:1 on white
      so light mode uses `#5C6B7F` (5.43:1). Signal bars clear the 3:1 required of a
      meaningful non-text element in both themes.
- [x] **PHG-4.2** Status as a 4px signal-coloured left edge on medication rows.
      Files: `styles.py` (`StatusEdgeDelegate`), `ui.py`
      Qt stylesheets cannot address a table row, so this is a `QStyledItemDelegate` painting
      column 0. The old full-row pink and green wash is gone, replaced by a near-invisible
      tint; the Status and Remaining text columns still carry the state, so nothing is
      conveyed by colour alone.
- [x] **PHG-4.3** Tabular figures, flat cards, accent tab rule, focus rings.
      Files: `styles.py`, `ui.py`
      Mono columns are id, dosage, date, time and countdown. Buttons are quiet by default
      with fill reserved for a real primary or destructive action, replacing a row of six
      identical blue blocks with no hierarchy. Dropped the `[text*="Delete"]`/`[text*="Cancel"]`
      /`[text*="Taken"]` attribute selectors, which were painting Cancel red and Mark Not
      Taken green.
- [x] **PHG-4.4** Empty states rewritten to name the action that fills them.
      Files: `dashboard.py`, `statistics_window.py`
- [x] **PHG-4.5** Screenshots regenerated in both themes.
      Files: `docs/screenshots/*.png`
      112 tests still green; stderr empty on both capture runs and on a real windowed launch.

Fixed in passing, because the same lines were already open:

- [x] **PHG-4.6** Tab labels no longer clip. `QTabBar` measures tab width from the widget
      font, so a weight set only in the stylesheet painted wider than what was measured and
      "Calendar / Daily View" lost a character off each end.
      Files: `styles.py`
- [x] **PHG-4.7** Checkbox state is visible again. Styling the parent drops Qt off native
      subcontrol painting, so every checkbox rendered as an empty box in both states: the
      statistics filter read "All Patients" while its own box looked unticked.
      Files: `styles.py`
- [x] **PHG-4.8** Calendar no longer speaks the app's signal colours by accident. Qt paints
      weekends red and ships green circle month arrows; red already means a missed dose here
      and green means taken. Weekends are muted, arrows are text chevrons.
      Files: `ui.py`
- [x] **PHG-4.9** Removed the decorative `+ ! > # %` glyph cycled by index on the dashboard
      tiles, which had no relationship to the number beside it.
      Files: `dashboard.py`

## Phase 5 — Statistics tab

- [x] **PHG-5.1** Charts inherit the theme. Six hardcoded light/dark colour pairs across
      three methods now read from the token set; no hex literal remains in any view module.
      Files: `statistics_window.py`
- [x] **PHG-5.2** The tab opens on All Patients over This Month instead of five zeros and two
      blank charts. The workaround in `tools/capture_screenshots.py` that set this state by
      hand before capturing has been deleted, so a regression would show up in the
      screenshots rather than being papered over.
      Files: `statistics_window.py`, `tools/capture_screenshots.py`
- [x] **PHG-5.3** Fixed colliding labels that rendered as "All PatientsFind Patient".
      Files: `patient_widgets.py`
- [ ] **PHG-5.4** Add an adherence-over-time line chart. The current pie says little.
      Files: `statistics_window.py`
      Done when: the chart plots the selected range day by day and its values match
      `calculate_statistics` for the same range.

## Phase 6 — Platform and packaging (not started)

- [x] **PHG-6.1** Platform font chain added. Qt resolves `font-family` left to right and warns
      for a leading name it cannot find, so the head of the chain is chosen by `sys.platform`
      rather than hoping one list suits every OS. Apple's `SF Pro Text` and `SF Mono` are not
      exposed to Qt's font database, which is why the macOS head is Helvetica Neue and Menlo.
      Files: `styles.py`
      Verified: stderr is empty on a real windowed launch and on both screenshot runs.
- [ ] **PHG-6.2** Verify or guard `plyer` desktop notifications and `QSoundEffect` playback
      on macOS. Both are wrapped in try/except at import, so they degrade rather than crash,
      but neither has been confirmed to actually work here.
      Files: `notification_manager.py`, `README.md`
      Done when: the report says which of the two work on macOS, with proof, and
      Known Limitations says so if either does not.
- [ ] **PHG-6.3** Bound the scheduler's working set.
      `get_pending_medications_for_scheduler` selects every not-taken dose with
      `medication_date <= today` and no lower bound, so it re-loads and re-iterates every
      historic missed dose once a minute forever. Harmless at 288 rows, linear growth after
      a year of use.
      Files: `database.py`, `scheduler.py`, `tests/test_database.py`
      Done when: the query has a lookback window, a test pins it, and a
      `# ponytail:` comment names the ceiling.
- [ ] **PHG-6.4** Build a PyInstaller one-file release with the icon embedded and attach the
      artefact to a GitHub release. This app cannot be hosted, so a download is the only way
      a reviewer runs it without a Python toolchain.
      Files: `pharmaguard.spec` (new), `README.md`
      Done when: the built binary launches on a machine with no Python installed and reaches
      the login screen.

## Phase 7 — Documentation (not started)

- [ ] **PHG-7.1** Write `docs/USER_GUIDE.md` covering the admin flow and the patient flow
      end to end. An earlier README claimed `documents/Admin_Manual.md` and
      `documents/User_Manual.md`; neither ever existed.
      Files: `docs/USER_GUIDE.md` (new), `README.md`
      Done when: someone who has never seen the app can follow it from login to marking a
      dose taken, and every screenshot it references exists.

## Phase 8 — Showcase polish: the surfaces no screenshot ever covered (done 2026-08-04)

Phase 4 restyled the six tabs. The three dialogs had never been captured even once, and
two tabs were only ever seen at a glance. Everything below was found by rendering the
surface and looking at it, not by reading the code.

- [x] **PHG-8.1** Give the reminder dialog a hierarchy and a signal.
      This is the app's whole reason to exist and its three buttons - Mark As Taken, Mute
      Sound, Close - render identically, so the one action that matters does not lead. The
      dialog also looks the same whether the dose is ten minutes away or already missed,
      which throws away the three-event model the scheduler works hard to produce.
      Files: `dialogs.py`, `styles.py`
      Done when: Mark As Taken is the only filled button, the dialog carries the event's
      signal colour as an edge, and a missed-dose reminder is distinguishable from a
      ten-minute warning in a greyscale screenshot.
- [x] **PHG-8.2** Rebuild the reminder dialog's detail block. It is currently eight
      `Label: value` lines in body text, so medicine, dosage and time - the only three
      things a patient acts on - carry no more weight than `Category`.
      Files: `dialogs.py`
      Done when: medicine and dosage read as the headline, the time is tabular, and the
      remaining fields are secondary.
- [x] **PHG-8.3** Finish the bilingual labels or drop them. Five read
      `Patient / პაციენტი`, `Medicine / წამალი`, `Dosage / დოზა`, `Date / თარიღი`,
      `Time / დრო`; two read `Taking Rule` and `Status` in English only. Half-translated is
      worse than either choice. The users are a Georgian clinic, so complete it.
      Files: `ui.py`, `dialogs.py`
      Done when: every field label in the Add Medication tab and the Edit dialog is
      bilingual, and the two files agree on the wording.
- [x] **PHG-8.4** Separate the clinical warning from the category. Both render as identical
      plain text under the form, so "Do not exceed 8 puffs daily" has the same weight as
      "Bronchodilator".
      Files: `ui.py`, `dialogs.py`
      Done when: the warning uses the amber signal treatment and the category does not.
- [x] **PHG-8.5** Make Save and Add Medication the primary buttons in their dialogs.
      Files: `dialogs.py`
      Done when: each dialog has exactly one filled button.
- [x] **PHG-8.6** Give the User Profile tables room. `users_table` and
      `medical_history_table` have no minimum height, so a five-patient clinic shows two
      rows behind a scrollbar and the Medical History table clips its last column header.
      Files: `user_profile.py`
      Done when: a five-patient seeded database shows all five without scrolling.
- [x] **PHG-8.7** Stop Activate and Deactivate competing. Both are filled, so neither leads
      and the destructive one does not stand out.
      Files: `user_profile.py`
      Done when: only the destructive action is filled.
- [x] **PHG-8.8** Use tabular figures in the remaining tables: ids and Created Date in the
      users table, timestamps in the audit table. Times already align in the daily view and
      these do not.
      Files: `user_profile.py`, `settings_tab.py`
      Done when: id and timestamp columns align vertically in all three tables.
- [x] **PHG-8.9** Right-size Restore Default Settings. A rare, mildly destructive action
      currently spans the full window width in amber, outweighing every setting above it.
      Files: `settings_tab.py`
      Done when: it sits right-aligned at its natural width.
- [x] **PHG-8.10** Give the audit table an empty state. It currently renders as a blank
      white box, which reads as broken rather than as "no entries match".
      Files: `settings_tab.py`
      Done when: an empty result explains itself and names the filter to widen.
Found and fixed while working the phase, because the screenshots showed them:

- [x] **PHG-8.12** Durations no longer run past their unit. `remaining_time_text` and the
      reminder banner both formatted hours unbounded, so a dose missed three weeks ago
      read "Overdue by 516h 7m" in the daily view and in the popup. One shared
      `format_duration` in `medication.py` now rolls minutes into hours into days, with
      both callers routed through it and 12 tests over the boundaries.
      Files: `medication.py`, `dialogs.py`, `tests/test_medication.py`
- [x] **PHG-8.13** The seeder no longer produces a clinic with zero missed doses. Today's
      past doses were marked Taken without exception, so a database seeded at any hour
      showed nothing overdue - and the screenshots of an adherence tracker carried no
      evidence that it tracks adherence. Today now follows the same ~85% rate as history,
      still deterministic under the fixed seed.
      Files: `seed_demo_data.py`
- [x] **PHG-8.14** README brought back in line with the tree: screenshot section rebuilt
      around the reminder popup, the stale "no export yet" limitation corrected (export
      exists), the audit claim narrowed to what is actually logged, the UTC decision
      recorded under Design decisions, and the test count and pasted pytest output
      refreshed from a real run.
      Files: `README.md`

- [x] **PHG-8.11** Add the dialogs to `docs/screenshots/`. `tools/capture_screenshots.py`
      walks the tab bar only, so the reminder popup - the single most demo-able moment in
      the app - appears nowhere in the README.
      Files: `tools/capture_screenshots.py`, `docs/screenshots/`, `README.md`
      Done when: the reminder, edit and copy-day dialogs are captured in both themes by the
      same command, with no real patient data.

---

## Already landed

Completed before this ledger was rewritten; original ids preserved.

- [x] **PG-1** Leaked credential database untracked; PBKDF2-HMAC-SHA256 (240k iterations,
      per-user salt) replacing unsalted SHA-256; legacy hashes still verify and are
      transparently upgraded on the next successful login; admin credentials moved to
      `PHARMAGUARD_ADMIN_USER` / `PHARMAGUARD_ADMIN_PASSWORD` with a labelled demo fallback;
      `hmac.compare_digest` throughout. (History purge remains open as `PHG-0.1`.)
- [x] **PG-2** `assets/` restored — `logo.svg` authored, `logo.png` and a multi-size
      `pharmaguard.ico` generated by `tools/build_icons.py`. `Requirments short.txt` and
      `GITHUB_UPLOAD_GUIDE.md` deleted.
- [x] **PG-3** `seed_demo_data.py` — deterministic synthetic data, so the repo never needs
      to ship a database.
- [x] **PG-4** Admin password reset no longer assigns a fixed `Patient123!` to every
      account; `generate_temporary_password()` produces a unique policy-compliant one-time
      password.
- [x] **PG-5** Scheduler rewritten from exact-minute equality to time windows — a delayed
      tick no longer silently drops a reminder forever. Injectable reference time for
      testing. (The resulting 1-minute grace window is `PHG-1.3`.)
- [x] **PG-6** Fixed a crash: a bare-hour time like `"8"` passed through
      `normalized_medicine_time()` unpadded and blew up `strptime`.
- [x] **PG-7** 112 tests across auth, database, medication maths and scheduler.
- [x] **PG-8** Notification sounds generated by `tools/build_sounds.py` (stdlib `wave`, no
      dependency) — the four WAVs the app referenced were absent.
- [x] **PG-9** Screenshots via `tools/capture_screenshots.py`, both themes.
- [x] **PG-10** README rewritten: architecture, design decisions, limitations.

## Deliberately out of scope

- **A web port.** PyQt5 is native. Rewriting for the browser is a different project, not a
  deployment. Screenshots, a GIF and a downloadable build are the presentation. Settled.
- **A server component or multi-machine sync.** The deployment target is one machine in one
  office with a single writer, which is the whole reason SQLite is the right call here.
- **Drug-interaction warnings.** Deriving them from `medicine_info.csv` would mean inventing
  clinical logic and presenting it as authoritative. Non-negotiable #5 forbids that, and this
  is the one domain where a plausible-looking wrong answer causes real harm.
- **Encryption at rest for the SQLite file.** Real protection needs OS keychain integration;
  a passphrase in the source would be theatre and would repeat the mistake this repo is
  still paying for.
- **Widget-level tests for every dialog.** The view layer is worth covering where it computes
  a number or writes an audit row (`PHG-3.3`, `PHG-1.5`); pytest-qt click simulation across
  all seven view modules would cost more than it proves.

## Resume bullets

- Hardened a live PyQt5 clinical application after a credential leak: migrated unsalted
  SHA-256 to salted PBKDF2-HMAC-SHA256 at 240k iterations with transparent per-login
  re-hashing so no user was forced to reset, moved admin credentials to the environment
  behind a labelled demo fallback, and replaced a committed patient database with a
  deterministic synthetic seeder. *(Earned by PG-1 through PG-4.)*
- Rewrote a medication reminder engine that compared `now == scheduled_time` — one delayed
  tick dropped a dose reminder permanently and silently — into window matching with an
  injectable clock, and pinned the three-event lifecycle with 11 tests that never touch the
  wall clock. *(Earned by PG-5, PG-7.)*
- NOT YET EARNED: "verified end to end with a recorded workflow demo and coverage on the
  clinical paths" — requires Phases 1-3. Today the scheduler still aborts its whole pass on
  one unparseable time value, the view layer has no tests, and the audit trail can fail
  without saying so.
