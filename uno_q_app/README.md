# Acrylic Pan UNO Q — dummy inference bring-up

This App runs without a KX134 sensor. The STM32 sketch emits one dummy case
number per second. The Linux application loads the existing
`apan_dummy_128x32x8` model, runs pure-Python inference, saves JSONL, and logs
expected/predicted class agreement. This validates STM32, Bridge, Linux and
model execution without pretending the input is a physical sensor waveform.

`model.npz` and `golden_outputs.json` are copied from `data/dummy_model` by
`scripts/deploy-uno-q-dummy.ps1`; they are intentionally not duplicated here.

Output inside the App data directory: `data/inference/dummy_results.jsonl`.

Dummy mode is selected by `APAN_DUMMY_MODE` in `sketch/sketch.ino`. Change it
to `false` only after the KX134 wiring is installed and checked.
