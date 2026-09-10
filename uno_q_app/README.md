# Acrylic Pan KX134 standalone App for UNO Q

UNO Q performs KX134 acquisition, impact detection, 400 × 300 mm position
inference, audio synthesis and web serving.

- KX134-1211 SPI mode 0: D10 CS, D11 COPI, D12 CIPO, D13 SCK; D2/INT1 is diagnostic only
- accelerometer Z axis, ±32 g, 25.6 kHz, no averaging
- 512 samples / 20 ms with 64 pre-trigger samples / 2.5 ms
- original trigger contract: jerk 700, level 200, confirmation 3000 within 16 samples
- STM32U585 DWT cycle-counter scheduling and direct GPIO SPI
- portable 714-feature, three-member 60-position density and direct XY ensemble
- 12-area probabilities are summed from the same 60-position distribution, so
  the graph, winning panel and heatmap cannot disagree
- browser pages for collection, inference, XY heatmap and two instrument modes

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

Deploy from the repository root:

```powershell
.\scripts\deploy-uno-q-dummy.ps1
```

The deployment updates application files without removing the remote `data`
directory.
