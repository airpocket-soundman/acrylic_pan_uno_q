# Acrylic Pan KX134 standalone App for UNO Q

UNO Q performs KX134 acquisition, impact detection, 400 × 300 mm position
inference, audio synthesis and web serving.

- KX134-1211 SPI mode 0: D10 CS, D11 COPI, D12 CIPO, D13 SCK; D2/INT1 is diagnostic only
- accelerometer Z axis, ±32 g, 25.6 kHz, no averaging
- 512 samples / 20 ms with 64 pre-trigger samples / 2.5 ms
- original trigger contract: jerk 700, level 200, confirmation 3000 within 16 samples
- STM32U585 DWT cycle-counter scheduling and direct GPIO SPI
- selectable 60-position TFLite models, with the 5.90 M-parameter embedded-FFT
  large FP16 model selected for new deployments
- 12-area probabilities are summed from the same 60-position distribution, so
  the graph, winning panel and heatmap cannot disagree
- browser pages for collection, inference, XY heatmap and two instrument modes
- GeneralUser GS 2.0.3 BETA SoundFont rendered at 44.1 kHz by FluidSynth, with
  the original oscillator retained only as a runtime fallback

The app serves port 8765. Open:

```text
http://<UNO-Q-IP>:8765/
http://<UNO-Q-IP>:8765/collector.html
http://<UNO-Q-IP>:8765/position.html
http://<UNO-Q-IP>:8765/instrument.html
http://<UNO-Q-IP>:8765/instrument-probability.html
```

Collection stores append-only KX134 events at:

```text
/home/arduino/ArduinoApps/acrylic-pan-dummy/data/training/kx134_events.jsonl
```

Training is intentionally not started by the web UI. Protect and copy the
JSONL to the PC, then retrain only when explicitly requested.

The selected model was evaluated on a complete-session held-out split covering
all 60 positions: 97.05% position top-1, 99.44% 12-area accuracy, 1.78 mm MAP
mean error, and 1.76 mm probability-weighted XY mean error. See
`../docs/uno-q-fft-hybrid-evaluation-20260911.md`.

Deploy over Wi-Fi from the repository root:

```powershell
.\scripts\deploy-uno-q-wifi.ps1 -Target arduino@<UNO-Q-IP>
```

The deployment updates application files without removing the remote `data`
directory.

The Wi-Fi deployment script also sets Docker's `unless-stopped` restart policy
on the main app and USB-camera brick. After deployment, powering on UNO Q starts
sensor inference, the web/audio endpoints, and camera streaming automatically.
The probability-performance page connects that camera and prefetches its chosen
instrument. Browsers still require one click on **演奏開始** to unlock audible
Web Audio output.

`camera-autoselect.compose.yaml` deliberately omits a fixed `/dev/videoN`
argument. Linux can renumber the same UVC camera after a cold boot; the camera
runner therefore discovers the active USB capture node on every container start.
