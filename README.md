# PharmaGuard

PharmaGuard is a Python desktop healthcare application for medication reminders, patient tracking, medical history, and medication statistics.

## Technologies

- Python 3
- PyQt5
- SQLite
- APScheduler
- Pandas
- Matplotlib
- Plyer
- PyQt5 Multimedia / QSoundEffect

## Features

- Admin and patient login
- Active/inactive patient accounts
- Strong password validation
- Add, edit, delete, search, and copy medication reminders
- Mark medications as Taken or Not Taken
- Calendar / Daily View with date, patient, status, search, sorting, and row limit filters
- Automatic reminder checks with APScheduler
- PyQt reminder popups
- Windows desktop notifications
- Custom notification sounds
- CSV medicine information import
- Patient medical history and diagnosis management
- Dashboard cards for medication overview
- Statistics tab with Matplotlib charts
- Light and Dark themes
- Settings tab
- Audit / activity log
- Admin and User manuals

## Project Structure

```text
PharmaGuard/
|-- main.py
|-- auth_manager.py
|-- database.py
|-- dashboard.py
|-- dialogs.py
|-- login_dialog.py
|-- medication.py
|-- notification_manager.py
|-- patient_widgets.py
|-- scheduler.py
|-- settings_tab.py
|-- statistics_window.py
|-- styles.py
|-- ui.py
|-- user.py
|-- user_profile.py
|-- medicine_info.csv
|-- requirements.txt
|-- assets/
|   |-- logo.ico
|   |-- logo.png
|   |-- pharmaguard.ico
|-- sounds/
|   |-- add_medication.wav
|   |-- checkin.wav
|   |-- missed_deadline.wav
|   |-- ten_min_before_checkin.wav
|-- documents/
|   |-- Admin_Manual.md
|   |-- User_Manual.md
```

## Installation

Open a terminal inside the project folder:

```powershell
cd C:\Users\PC\Documents\GitHub\Project_1\PharmaGuard
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Running

```powershell
python main.py
```

The SQLite database is created or upgraded automatically when the application starts.

## Default Admin Login

```text
Username: Admin1
Password: Pharmguard1
```

## Notes

- `pharma_guard.db` is ignored by Git because it is a local runtime database.
- `.venv/`, `__pycache__/`, and temporary files should not be uploaded.
- Sound and asset files should be uploaded because the application uses them.
