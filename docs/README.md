# Documentation index

This directory contains current build instructions, model evaluations, contest material, and historical engineering notes. Start with the current documents below; the remaining files are retained for reproducibility and design history.

## Build and operate the current UNO Q system

- [UNO Q application guide](../uno_q_app/README.md)
- [KX134 sensor wiring](uno-q-sensor-wiring.md)
- [Bill of materials](uno-q-bom.md)
- [USB camera and powered-hub setup](uno-q-usb-camera.md)
- [Collector quick start](collector-quickstart.md)
- [Implementation handoff and live-system state](uno-q-handoff.md)

## AI models and evaluation

- [Embedded-FFT model evaluation](uno-q-fft-hybrid-evaluation-20260911.md)
- [CPU/GPU model benchmark](uno-q-cpu-gpu-benchmark-20260911.md)
- [CPU/GPU model requirements](uno-q-cpu-gpu-model-requirements.md)
- [Position inference design](position-inference.md)
- [Real-model training notes](real-model-training.md)
- [Data strategy](data-strategy.md)

The current evaluation contract uses complete-session separation and covers all 60 positions in training, validation, and held-out test.

## Contest and presentation

- [Japanese Hackster Story preview](hackster-story-ja.html)
- [Story media placement plan](hackster-story-media-plan.md)
- [Hackster-ready figures](assets/hackster/)
- [Contest submission checklist](../CONTEST_SUBMISSION.md)

## Simulation and physical design

- [Simulation method](simulation-method.md)
- [Simulation environment](simulation-environment.md)
- [3D solid finite-element model](solid-fem.md)
- [CalculiX analysis](calculix-analysis.md)
- [High-frequency CalculiX analysis](calculix-highfrequency.md)
- [XY-grid CalculiX analysis](calculix-xy-grid.md)
- [Sensor response](sensor-response.md)
- [Mechanical/electrical design](design.md)

Large generated solver outputs under `web/assets/simulation/` are retained as reproducibility evidence. The Story should link representative images and animations rather than asking readers to navigate raw solver files.

## Historical and diagnostic notes

Files describing earlier sensors, model formats, bring-up experiments, migration work, or superseded sampling approaches remain available for traceability. They are not the primary build path for the current KX134/UNO Q system.

- `kx132-1211-evk-wiring.md`
- `uno-q-dummy-bringup.md`
- `uno-q-migration.md`
- `sampling-experiment-20260718.md`
- `trigger-threshold-analysis-20260718.md`
- `pc-xy-regression.md`
- `solist-*`
