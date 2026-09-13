from __future__ import annotations

import sys
import unittest
import wave
import hashlib
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "uno_q_app" / "python"))
from audio_synth import SAMPLE_RATE_HZ, SOUNDFONT_PATH, _midi_note, synthesize_note  # noqa: E402


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

    def test_generaluser_soundfont_is_packaged_and_identified(self):
        value = SOUNDFONT_PATH.read_bytes()
        self.assertEqual(value[:4], b"RIFF")
        self.assertIn(b"GeneralUser GS 2.0.3 BETA", value[:4096])
        self.assertEqual(hashlib.sha256(value).hexdigest(),
                         "e2ed326ff44d15f78f2fdc72403b6fa6b77ee7266d3aad0d2198bc95797bc66c")

    def test_note_names_map_to_midi_with_octave_transpose(self):
        self.assertEqual(_midi_note("C4", 0), 60)
        self.assertEqual(_midi_note("A#5", -1), 70)
        self.assertEqual(_midi_note("B7", 2), 127)


if __name__ == "__main__":
    unittest.main()
