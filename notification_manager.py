"""
Notification and sound handling for PharmaGuard.

This module keeps sound playback and Windows desktop notifications separate
from the user interface code.
"""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QObject, QUrl

try:
    from PyQt5.QtMultimedia import QSoundEffect
except Exception:
    QSoundEffect = None

try:
    from plyer import notification
except Exception:
    notification = None


class NotificationManager(QObject):
    """Plays custom sounds and shows Windows desktop notifications."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.base_dir = Path(__file__).resolve().parent
        self.sounds_dir = self.base_dir / "sounds"
        self.icon_path = self.base_dir / "assets" / "pharmaguard.ico"
        self.current_sound: Optional[QSoundEffect] = None
        self.sounds_enabled = True
        self.desktop_enabled = True
        self.volume = 0.85

    def apply_settings(self, sounds_enabled: bool = True, desktop_enabled: bool = True, volume: int = 85) -> None:
        self.sounds_enabled = sounds_enabled
        self.desktop_enabled = desktop_enabled
        self.volume = max(0, min(volume, 100)) / 100

    def play_sound(self, filename: str) -> None:
        """
        Play one custom WAV sound.

        Missing files or unavailable multimedia support should never crash the
        application; they only print a warning.
        """
        if not self.sounds_enabled:
            return

        path = self.sounds_dir / filename
        if not path.exists():
            print(f"Warning: sound file missing: {path}")
            return

        if QSoundEffect is None:
            print("Warning: QSoundEffect is not available. Sound was not played.")
            return

        self.stop_current_sound()
        sound = QSoundEffect(self)
        sound.setSource(QUrl.fromLocalFile(str(path)))
        sound.setVolume(self.volume)
        sound.setLoopCount(1)
        sound.play()
        self.current_sound = sound

    def stop_current_sound(self) -> None:
        """Stop only the currently playing custom sound."""
        if self.current_sound is not None:
            self.current_sound.stop()
            self.current_sound = None

    def show_desktop_notification(self, title: str, message: str, timeout: int = 8) -> None:
        """Show a Windows desktop notification through plyer."""
        if not self.desktop_enabled:
            return

        if notification is None:
            print("Warning: plyer is not available. Desktop notification was not shown.")
            return

        try:
            notification_message = message if title == "PharmaGuard" else f"{title}\n{message}"
            notify_kwargs = {
                "title": "PharmaGuard",
                "message": notification_message,
                "app_name": "PharmaGuard",
                "timeout": timeout,
            }
            if self.icon_path.exists():
                notify_kwargs["app_icon"] = str(self.icon_path)

            notification.notify(
                **notify_kwargs
            )
        except Exception as error:
            print(f"Warning: desktop notification failed: {error}")

    def notify_medication_added(self, medicine_name: str, patient_name: str) -> None:
        """Play and show notification after adding a medication."""
        self.play_sound("add_medication.wav")
        self.show_desktop_notification(
            "Medication Added",
            f"{medicine_name} was added for {patient_name}.",
        )

    def notify_medication_taken(self, medicine_name: str, patient_name: str) -> None:
        """Play and show notification after marking a medication as taken."""
        self.play_sound("checkin.wav")
        self.show_desktop_notification(
            "Medication Taken",
            f"{medicine_name} was marked as taken for {patient_name}.",
        )
