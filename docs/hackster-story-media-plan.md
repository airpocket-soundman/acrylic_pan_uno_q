# Hackster Story media placement

Use the PNG files in the Story body and attach the matching SVG files as downloadable source artwork. Keep each image full-width. The bracketed lines below are deliberate editor markers to be replaced by uploaded media before final publication.

## OVERVIEW

Place immediately after the first overview paragraph:

`[INSERT PHOTO 1 HERE — finished 400 × 300 mm ModalTouch instrument with UNO Q, KX134 and camera visible]`

Caption: **ModalTouch turns a plain acrylic sheet into a camera-mapped, AI musical surface.**

Use an actual project photograph rather than a rendered mock-up. The existing `docs/assets/hackster/modal-touch-cover.png` can remain the cover until this photograph is ready.

## THE AI IDEA: EXPAND ONE VIBRATION SIGNAL INTO COORDINATE SPACE

Place after the paragraph ending “AI is the enabling mechanism, not an accessory added after sensing.”:

`[INSERT FIGURE 1 HERE — one-sensor-ai-expansion.png]`

Caption: **One fixed accelerometer records a position-dependent modal signature. An embedded-FFT neural network expands that waveform into a 60-position probability field and XY estimate.**

Files:

- `docs/assets/hackster/one-sensor-ai-expansion.png`
- `docs/assets/hackster/one-sensor-ai-expansion.svg`

## SIMULATION BEFORE BUILDING

Keep the existing simulation GIF after the simulation explanation:

`[INSERT ANIMATION HERE — acrylic-pan-12-hit-vibration-modes.gif]`

Caption: **Twelve simulated strike locations observed from one fixed center sensor; the common color scale makes the distinct modal mixtures directly comparable.**

Optionally add one still before the GIF: `web/assets/simulation/5mm-400x300/solid3d/solid3d-12-hit-stills.svg`.

## WHY ARDUINO UNO Q

Place after the MCU/MPU responsibility lists:

`[INSERT FIGURE 2 HERE — modal-touch-system-architecture.png]`

Caption: **The STM32U585 captures each impact deterministically, while the QRB2210 runs AI inference, camera streaming, audio synthesis and the Wi-Fi application. No cloud inference is required.**

Files:

- `docs/assets/hackster/modal-touch-system-architecture.png`
- `docs/assets/hackster/modal-touch-system-architecture.svg`

## HARDWARE AND WIRING

Place after the SPI signal list:

`[INSERT FIGURE 3 HERE — uno-q-kx134-wiring.png]`

Caption: **Complete 3.3 V SPI wiring between Arduino UNO Q and the KX134-1211 evaluation board.**

Then add an actual close-up photograph:

`[INSERT PHOTO 2 HERE — keyed cable, adapter PCB and mounted KX134 close-up]`

Caption: **The keyed adapter makes the high-speed SPI connection repeatable and prevents connector reversal.**

## DATA COLLECTION: 60 ANCHORS FOR A CONTINUOUS SURFACE

Place after the description of the 60 anchors:

`[INSERT FIGURE 4 HERE — xy-training-layout.png]`

Caption: **Each of the twelve playable areas contributes one center and four near-corner anchors, giving 60 labelled positions over the 400 × 300 mm surface.**

Add a collector-page screenshot after the train/validation/test split paragraph:

`[INSERT SCREENSHOT 1 HERE — UNO Q collector page showing a captured KX134 waveform]`

Caption: **The UNO Q collector stores labelled waveforms and lets the operator inspect or reject individual strikes before PC training.**

## MODELS AND INDEPENDENT TEST RESULTS

Place `one-sensor-ai-expansion.png` only in THE AI IDEA; do not repeat it here. Do not use `pc-xy-regression-comparison.png`: it compares other platforms and PC models, and the Story describes only the Arduino UNO Q implementation.

The result text must state that training, validation and held-out test each cover all 60 positions. Current held-out results for the selected large embedded-FFT FP16 model are 97.05% 60-position top-1, 99.44% 12-area accuracy, 1.78 mm MAP mean error and 1.76 mm expected-XY mean error.

## VERY FAST AI INFERENCE ON UNO Q

Place after the explanation of preloaded models and packed Bridge chunks:

`[INSERT FIGURE 6 HERE — uno-q-low-latency-flow.png]`

Caption: **The latency-critical path uses deterministic acquisition, packed transfer, warmed TFLite kernels, event-driven delivery and cached audio.**

Files:

- `docs/assets/hackster/uno-q-low-latency-flow.png`
- `docs/assets/hackster/uno-q-low-latency-flow.svg`

Do not claim an UNO Q timing for the new 11.82 MB large FFT model until it has been deployed and measured. Existing timing figures should be labelled as measurements of the earlier standard and temporal candidates.

## CAMERA-MAPPED PROBABILITY HEAT MAP

Place after the camera mapping paragraph:

`[INSERT SCREENSHOT 2 HERE — performance page showing the transparent 60-point heat map aligned over the acrylic surface]`

Caption: **The same 60-position probability distribution drives the graph, winner outline, area result and perspective-correct camera overlay.**

Avoid screenshots containing a face or unrelated workbench clutter. Frame the acrylic surface, overlay and essential controls.

## AUDIO GENERATED ON UNO Q

Place a compact screenshot of the instrument selection controls if space allows:

`[OPTIONAL SCREENSHOT — instrument and song-guide controls]`

Caption: **FluidSynth renders GeneralUser GS instruments on UNO Q and caches each note for responsive playback.**

## BUILD AND RUN / final proof

Place the real-device demonstration video at the very top of the Story, directly under the title and above OVERVIEW, so readers see the working instrument first:

`[INSERT VIDEO HERE — one continuous shot: strike several areas and hear the UNO-Q-generated notes; the optional camera overlay may appear]`

Caption: **End-to-end demonstration: one accelerometer, on-board AI decoding on Arduino UNO Q, and UNO-Q-generated audio.**

This video is the strongest proof of completion and should take priority over additional simulation images.
