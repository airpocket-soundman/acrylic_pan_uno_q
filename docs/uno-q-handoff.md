# UNO Q implementation handoff

Last updated: 2026-09-11 (JST)

## Current deployed state

- Target UNO Q during development: `192.168.50.166`
- Web server: `http://192.168.50.166:8765/`
- KX134-1211 is detected over SPI (`WHO_AM_I = 0x46`).
- Acquisition runs at 25,600 Hz, +/-32 g, 512 samples/event with 64 pre-trigger samples.
- Five-second hardware check after the latest deployment captured 128,000 samples with zero missed sample periods.
- The UNO Q Linux side hosts every application HTML page, the 400 x 300 position model, inference APIs, data collection storage, and WAV synthesis.
- The client browser only renders the UI, decodes/plays UNO-Q-generated WAV data, and optionally supplies/displays the PC camera stream.
- Both instrument pages preload the active notes from `/api/audio/note.wav`; generated WAV data is cached on the UNO Q and in the browser.
- Inference delivery uses a blocking condition/long-poll endpoint instead of fixed-interval polling.
- The MCU sends a captured waveform as eight packed 64-sample chunks instead of 512 individual Bridge notifications.
- Training-data collection remains append-only. Deployment does not delete the remote `data` directory, and there is no automatic training pipeline in the UI.

## Latest measurements

- KX134 read benchmark: 1,000 Z-axis reads in 15,218 us.
- Portable 60-position ensemble inference: about 25.7 ms (`inference_us`, parity case on UNO Q).
- Cold WAV HTTP request: 73 ms in the latest check.
- Warm UNO-Q WAV cache request: 24 ms in the latest check. Normal performance preloads the WAV, so hit-time playback starts from a decoded browser `AudioBuffer` rather than waiting for HTTP or synthesis.
- Python syntax check and `test_uno_q*.py`: 12 tests passed.

## Remaining verification/work

1. With the acrylic panel attached, make one real strike and verify that the new `on_capture_chunk` callback completes one 512-sample event, inference advances exactly once, and sound plays once.
2. Measure strike-to-audio latency with a real strike. The remaining expected contributors are about 17.5 ms of post-trigger capture, the 115,200-baud MCU/Linux Bridge transfer, roughly 26 ms model inference, Wi-Fi/UI delivery, and the browser audio device buffer.
3. If transfer latency is still excessive, investigate a coordinated higher Bridge UART baud rate or a lower-overhead MCU/Linux transport. Do not change only the MCU baud; both ends must match.
4. Collect native KX134 training sessions over the full 400 x 300 panel, then retrain and validate the 12-area, 60-position probability/pseudo-XY, and direct-XY models on the PC when explicitly requested.
5. Compare predicted panel, maximum-probability panel, graph, and heat-map overlay against the new native KX134 validation set. They now share the same 60-position distribution, but accuracy still depends on native training data.
6. The probability page's optional camera image currently comes from the PC camera server. The application and audio require no PC service; only that optional camera source does.

## Resume checklist

1. Open `http://192.168.50.166:8765/instrument-probability.html` and perform a hard refresh if an older tab remains open.
2. Confirm `/api/status` reports `sensor_ready: true`, `sample_rate_hz: 25600`, and `missed_data_ready: 0` after startup.
3. Start performance, wait for note preloading to finish, then make one strike while watching the inference sequence and application log.
4. Preserve any files below the UNO Q app's `data/training` directory before doing device replacement or manual cleanup.
