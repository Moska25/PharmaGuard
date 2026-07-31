# GitHub Upload Guide

Upload the `PharmaGuard` project folder to GitHub.

## Upload These Files

```text
main.py
auth_manager.py
database.py
dashboard.py
dialogs.py
login_dialog.py
medication.py
notification_manager.py
patient_widgets.py
scheduler.py
settings_tab.py
statistics_window.py
styles.py
ui.py
user.py
user_profile.py
medicine_info.csv
requirements.txt
README.md
.gitignore
GITHUB_UPLOAD_GUIDE.md
```

## Upload These Folders

```text
assets/
sounds/
documents/
```

## Do Not Upload

```text
.venv/
__pycache__/
pharma_guard.db
user_info.txt
*.log
*.tmp
```

## Why Not Upload The Database?

`pharma_guard.db` is a local SQLite runtime file. PharmaGuard creates and upgrades the database automatically when the app starts, so each user can have their own local data.

## Recommended Git Commands

Run these commands from:

```powershell
cd C:\Users\PC\Documents\GitHub\Project_1\PharmaGuard
```

Then:

```powershell
git init
git add .
git commit -m "Initial PharmaGuard project"
git branch -M main
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with your repository URL from GitHub.
