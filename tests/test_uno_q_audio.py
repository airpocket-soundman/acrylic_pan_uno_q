from __future__ import annotations

import sys
import unittest
import wave
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app" / "python"))
from audio_synth import SAMPLE_RATE_HZ, synthesize_note  # noqa: E402


class UnoQAudioTests(unittest.TestCase):
    def test_uno_q_synthesizes_valid_pcm_wav(self):
        value = synthesize_note({"note": "C4", "instrument": "steel_drum", "velocity": ".8"})
        self.assertEqual(value[:4], b"RIFF")
        with wave.open(BytesIO(value), "rb") as stream:
            self.assertEqual(stream.getnchannels(), 1)
            self.assertEqual(stream.getsampwidth(), 2)
            self.assertEqual(stream.getframerate(), SAMPLE_RATE_HZ)
            self.assertGreater(stream.getnframes(), SAMPLE_RATE_HZ // 2)

    def test_supported_instruments_are_distinct(self):
        results = {name: synthesize_note({"note": "A4", "instrument": name})
                   for name in ("steel_drum", "piano", "harpsichord", "guitar", "drums")}
        self.assertEqual(len({value[44:400] for value in results.values()}), len(results))


if __name__ == "__main__":
    unittest.main()
