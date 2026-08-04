"""
Generate the notification WAV files in sounds/.

The app references four sounds by name. Without them every reminder is silent,
so they are synthesised here with the standard library rather than shipping
binary audio of unclear licence.

    python tools/build_sounds.py

Each cue is a short blend of sine tones with an exponential decay, so it reads
as a soft chime rather than a beep.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SOUNDS = Path(__file__).resolve().parent.parent / "sounds"
SAMPLE_RATE = 44_100
AMPLITUDE = 0.32

# name -> sequence of (frequency_hz, duration_seconds)
# Rising intervals read as informational; the falling minor third reads as a
# warning, which is what a missed dose should sound like.
CUES = {
    "add_medication": [(660, 0.09), (880, 0.16)],
    "checkin": [(880, 0.11), (1174, 0.11), (1318, 0.22)],
    "ten_min_before_checkin": [(784, 0.10), (988, 0.20)],
    "missed_deadline": [(587, 0.16), (494, 0.16), (392, 0.34)],
}


def tone(frequency: float, duration: float) -> list[float]:
    """One decaying sine tone with a short fade-in to avoid a click."""
    total = int(SAMPLE_RATE * duration)
    attack = max(1, int(SAMPLE_RATE * 0.005))
    samples = []
    for index in range(total):
        progress = index / total
        envelope = math.exp(-4.0 * progress)
        if index < attack:
            envelope *= index / attack
        samples.append(math.sin(2 * math.pi * frequency * index / SAMPLE_RATE) * envelope)
    return samples


def write_wav(name: str, sequence) -> Path:
    samples: list[float] = []
    for frequency, duration in sequence:
        samples.extend(tone(frequency, duration))

    peak = max(abs(value) for value in samples) or 1.0
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, value / peak)) * AMPLITUDE * 32767))
        for value in samples
    )

    destination = SOUNDS / f"{name}.wav"
    with wave.open(str(destination), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(frames)
    return destination


def main() -> int:
    SOUNDS.mkdir(exist_ok=True)
    for name, sequence in CUES.items():
        path = write_wav(name, sequence)
        print(f"  {path.name}  ({path.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
