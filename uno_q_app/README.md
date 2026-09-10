# Acrylic Pan MPU9250 standalone App for UNO Q

This App completes acquisition, guided data collection, training, inference and
web serving on the UNO Q itself.

- MPU9250 SPI mode 3: D10 CS, D11 COPI, D12 CIPO, D13 SCK, D8 DATA_RDY
- Accelerometer-only, ±16 g, 4 kHz, 1.046 kHz bandwidth
- sampling is synchronized to the MPU9250 DATA_RDY interrupt; no multi-sample averaging
- 80-sample / 20 ms events with 10 pre-trigger samples
- 12-area classification
- 60-position probability model and probability-weighted pseudo XY
- dedicated direct XY regression MLP (120-384-192-96-2, 139,106 trainable parameters)
- guided 400 × 300 mm / 60-position collection and on-device retraining
- inference, position heatmap, class instrument and probability instrument pages
- browser audio is rendered as PCM/WAV by UNO Q and delivered per note; the browser only decodes and plays it
- the UNO Q Wi-Fi page embeds the PC MJPEG server (`192.168.50.177:8878`) in an iframe

The initial model and `mpu9250_training_seed.npz` are generated from 7,132
measured KX134 events after bandwidth limiting, 4 kHz resampling, ±16 g clipping
and MPU9250 quantization:

```powershell
D:\GitHub\acrylic_pan\.venv\Scripts\python.exe scripts\train_mpu9250_uno_q_models.py
```

The conversion is an optimistic domain approximation. Use the collection page
with the installed MPU9250 and complete the PC retraining workflow below before
treating physical position accuracy as calibrated. The direct-XY network keeps
the expressive UNO Q architecture; it is not reduced to the legacy MCU-sized
fixed-hidden-layer model.

The App serves port 8765. Main pages are `/`, `/collector.html`,
`/position.html`, `/instrument.html`, and `/instrument-probability.html`.

## Real MPU9250 collection and PC retraining

Open `http://<UNO-Q-IP>:8765/collector.html`, select **all 60 positions**, and
collect at least 5 events per position (50 is recommended). Each accepted event
is labeled with its 12-area class and exact 400 x 300 mm target coordinate, then
appended on the UNO Q to:

```text
/home/arduino/ArduinoApps/acrylic-pan-dummy/data/training/mpu9250_events.jsonl
```

Synchronization, PC training, validation, and deployment are intentionally not
started from the web UI. Perform each operation only when explicitly requested,
after protecting the captured JSONL and reviewing the held-out evaluation.

For the camera iframe on this PC, start the LAN MJPEG service before opening
the UNO Q page:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install opencv-python
.\scripts\start_pc_camera.ps1
```

Then open `http://192.168.50.160:8765/`. The PC camera stream is served from
`http://192.168.50.177:8878/`; its address can be changed in the page if DHCP
assigns the PC a different address.

`/instrument-probability.html` uses the same PC MJPEG stream as its camera
background. The 60-position density heatmap, winning 12-area rectangle and
pseudo-XY marker are drawn on a transparent canvas above it. Four-point
alignment maps panel corners in the order top-left, top-right, bottom-right,
bottom-left.
