from __future__ import annotations

import io
import re
import wave

import numpy as np


SAMPLE_RATE_HZ = 24_000
NOTE_PATTERN = re.compile(r"^([A-G])(#?)([2-7])$")
SEMITONES = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def _number(options: dict[str, str], name: str, default: float,
            minimum: float, maximum: float) -> float:
    try:
        value = float(options.get(name, default))
    except (TypeError, ValueError):
        value = default
    return min(maximum, max(minimum, value))


def _frequency(note: str, transpose: int) -> float:
    match = NOTE_PATTERN.match(note)
    if not match:
        return 440.0
    semitone = SEMITONES[match.group(1)] + bool(match.group(2)) + (int(match.group(3)) + transpose - 4) * 12
    return 440.0 * 2.0 ** (semitone / 12.0)


def _envelope(length: int, attack: float, decay: float, sustain: float,
              release: float) -> np.ndarray:
    counts = [max(1, int(value * SAMPLE_RATE_HZ)) for value in (attack, decay, release)]
    sustain_count = max(0, length - sum(counts))
    return np.concatenate((
        np.linspace(0.0, 1.0, counts[0], endpoint=False),
        np.linspace(1.0, sustain, counts[1], endpoint=False),
        np.full(sustain_count, sustain),
        np.linspace(sustain, 0.0, counts[2]),
    ))[:length]


def synthesize_note(options: dict[str, str]) -> bytes:
    """Render one note on UNO Q and return mono 16-bit PCM WAV bytes."""
    instrument = options.get("instrument", "steel_drum")
    transpose = int(_number(options, "transpose", 0, -2, 2))
    frequency = _frequency(options.get("note", "A4"), transpose)
    velocity = _number(options, "velocity", .75, .05, 1.0)
    volume = _number(options, "volume", .70, 0.0, 1.0)
    brightness = _number(options, "brightness", .65, 0.0, 1.0)
    attack = _number(options, "attack", .005, .001, .5)
    decay = _number(options, "decay", .35, .03, 1.5)
    sustain = _number(options, "sustain", .18, 0.0, 1.0)
    release = _number(options, "release", .90, .03, 3.0)
    duration = min(4.5, attack + decay + release + .12)
    count = max(1, int(duration * SAMPLE_RATE_HZ))
    time = np.arange(count, dtype=np.float64) / SAMPLE_RATE_HZ
    envelope = _envelope(count, attack, decay, sustain, release)

    if instrument == "steel_drum":
        partials = ((1.0, .78), (2.0, .18), (3.01, .08), (4.2, .04))
        signal = sum(weight * np.sin(2 * np.pi * frequency * ratio * time) *
                     np.exp(-time * (1.2 + index * (1.4 - brightness)))
                     for index, (ratio, weight) in enumerate(partials))
    elif instrument == "harpsichord":
        harmonics = 3 + int(brightness * 7)
        signal = sum(np.sin(2 * np.pi * frequency * harmonic * time) / harmonic
                     for harmonic in range(1, harmonics + 1)) * np.exp(-time * 3.5)
    elif instrument == "piano":
        signal = (np.sin(2 * np.pi * frequency * time) +
                  .24 * np.sin(2 * np.pi * frequency * 2.01 * time) +
                  .08 * np.sin(2 * np.pi * frequency * 3.03 * time)) * np.exp(-time * .85)
    elif instrument == "guitar":
        signal = sum((.72 / harmonic) * np.sin(2 * np.pi * frequency * harmonic * time)
                     for harmonic in range(1, 7)) * np.exp(-time * 2.1)
    else:
        area = int(_number(options, "area", 0, 0, 11))
        sweep = frequency * (.35 + .65 * np.exp(-time * 18.0))
        phase = 2 * np.pi * np.cumsum(sweep) / SAMPLE_RATE_HZ
        signal = np.sin(phase) * np.exp(-time * 12.0)
        if area % 3:
            signal += np.random.default_rng(area).normal(0.0, .25, count) * np.exp(-time * 22.0)

    signal *= envelope * velocity * volume
    echo_mix = _number(options, "echo_mix", .18, 0.0, .75)
    echo_delay = int(_number(options, "echo_delay", .18, .03, .8) * SAMPLE_RATE_HZ)
    echo_feedback = _number(options, "echo_feedback", .24, 0.0, .8)
    mixed = signal.copy()
    gain = echo_mix
    for repeat in range(1, 4):
        offset = echo_delay * repeat
        if offset >= count:
            break
        mixed[offset:] += signal[:-offset] * gain
        gain *= echo_feedback
    peak = max(1.0, float(np.max(np.abs(mixed))) / .96)
    pcm = np.rint(np.clip(mixed / peak, -1.0, 1.0) * 32767.0).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(SAMPLE_RATE_HZ)
        stream.writeframes(pcm.tobytes())
    return output.getvalue()
