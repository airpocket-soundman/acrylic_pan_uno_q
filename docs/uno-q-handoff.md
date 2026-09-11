# UNO Q implementation handoff

Last updated: 2026-09-11 (JST)

## Current deployed state

- Primary development network address previously used: `192.168.50.166`
- Secondary development environment address (2026-09-11): `192.168.101.85`
- Secondary web server: `http://192.168.101.85:8765/`
- Wi-Fi management from this PC is available with `ssh arduino@192.168.101.85` using the registered SSH key. The Wi-Fi password is intentionally not stored in this repository.
- NetworkManager keeps the primary profile at autoconnect priority 100 and the secondary profile at priority 10. This makes the original development network preferred when both are available.
- KX134-1211 is detected over SPI (`WHO_AM_I = 0x46`).
- Acquisition runs at 25,600 Hz, +/-32 g, 512 samples/event with 64 pre-trigger samples.
- Five-second hardware check after the latest deployment captured 128,000 samples with zero missed sample periods.
- The UNO Q Linux side hosts every application HTML page, the 400 x 300 position model, inference APIs, data collection storage, and WAV synthesis.
- The client browser only renders the UI and decodes/plays UNO-Q-generated WAV data. The current repository revision moves camera ownership to the UNO Q Linux MPU through the official video brick; hardware verification awaits the powered USB-C hub and UVC camera connection.
- The probability-instrument UI can select either a camera attached to the development PC or the UNO Q camera stream. `scripts/run-dual-camera-ui.ps1` exposes the UNO Q UI at localhost over Wi-Fi so browser camera permission works. Eight-point alignment is saved separately for each source: four panel corners plus the left/right endpoints of both horizontal row dividers. Divider endpoints are stored as independent ratios along the two vertical edges.
- The probability-instrument screen is fixed to the 400 x 300 mm panel, internal KX134 SPI connection, and UNO Q Linux position model. Those three selectors are retained only as hidden compatibility nodes for the shared browser code and are not user-facing controls.
- NPU execution was requested, but the current UNO Q Debian image exposes the Adreno 702 through Mesa OpenCL and does not contain QNN/SNPE libraries or a FastRPC/NPU device node. The deployed model therefore remains NumPy CPU inference and reports `inference_accelerator: cpu_numpy`; do not label it as NPU execution. Moving it to Hexagon requires a supported Qualcomm runtime/toolchain for QRB2210, model conversion, parity validation, and deployment support not present in the current image. GPU/OpenCL is the available hardware-acceleration fallback if NPU access remains unavailable.
- CPU向けとGPU向けに別々に最適化した次期モデルは、元のKX134実測データが保存されている別開発環境で学習・変換する。UNO Qが接続されていない環境では精度評価とTFLite parity確認までを行い、実際のCPU/GPU delegate、遅延、負荷、カメラ同時動作はこのセカンダリ環境で検証する。入出力契約、成果物、合否条件は [UNO Q CPU/GPU向け座標推論モデル要件](uno-q-cpu-gpu-model-requirements.md) を参照する。
- Commit `91f10cd` のCPU dynamic MLPとGPU FP16 CNNをUNO Qで評価した。GPU CNNはAdreno 702へ実委譲できたが、前処理込みp95はGPU 16.94 ms、同じCNNのCPU/XNNPACK 2.57 msだった。CPU用MLPは1.84 msだが固定テストセット精度がCNNより低い。現候補ではGPU CNNをCPU/XNNPACKで実行する構成が最良である。ただし受領parityは48格子点×2件だけで中心12点を含まず、全60点の実機照合は未完了。詳細は [UNO Q CPU/GPUモデル実機評価](uno-q-cpu-gpu-benchmark-20260911.md) を参照する。稼働モデルはまだ切り替えていない。
- 時間波形CNNへFFT枝を加えたモデルも`uno_q_fft_candidates/`に生成した。標準FP16版は生の512点を入力し、TFLite内部でHann窓付きRFFTを実行する。時間CNN 85%＋FFT標準版15%のensemble（5.57 MB）は、従来CNNに対して60点top-1 97.95%→98.01%、12エリア98.85%→98.95%、Expected XY 1.86→1.83 mmへ改善した。融合比率は検証セッションのみで決定した。FFT標準単体はMAP平均誤差を1.91→1.56 mmへ改善し、590万パラメータの大型版は改善しなかった。詳細は [UNO Q FFT内蔵ハイブリッドモデル評価](uno-q-fft-hybrid-evaluation-20260911.md) を参照する。実機遅延と中央12点を含む別セッション評価までは配備モデルを切り替えない。
- CPU/GPU候補の再学習は完了した。成果物は `uno_q_model_candidates/`、再生成スクリプトは `scripts/train_uno_q_cpu_gpu_models.py`。11セッション7,132打点をセッション単位で学習4,745／検証480／独立テスト1,907へ分割した。CPU採用候補は動的量子化MLP（182,392 bytes、60点96.70%、12エリア98.69%、MAP平均2.73 mm）、GPU採用候補はFP16 Conv2D（2,174,572 bytes、60点97.95%、12エリア98.85%、MAP平均1.91 mm）。INT8 CPU版は精度・parity低下のため不採用。GPU delegateでの実行可否と速度はUNO Q実機で未確認。
- Both instrument pages preload the active notes from `/api/audio/note.wav`; generated WAV data is cached on the UNO Q and in the browser.
- Inference delivery uses a blocking condition/long-poll endpoint instead of fixed-interval polling.
- The MCU sends a captured waveform as eight packed 64-sample chunks instead of 512 individual Bridge notifications.
- Training-data collection remains append-only. Deployment does not delete the remote `data` directory, and there is no automatic training pipeline in the UI.

## Secondary-environment verification (2026-09-11)

- The `Acrylic Pan XY Instrument` app is installed at `/home/arduino/ArduinoApps/acrylic-pan-dummy` and was started successfully.
- The Web UI and `/api/status` are reachable over Wi-Fi at `192.168.101.85:8765`.
- The model `acrylic_pan_position_400x300x5_grid_v7_portable` loads and inference is enabled.
- After a complete MCU firmware upload, `/api/status` reports `sensor_ready: true`, `sample_rate_hz: 25600`, 127,992 acquired samples, and zero missed sample periods. The earlier `sensor_ready: false` reading was taken while the MCU upload/start sequence had not completed; it was not a wiring failure.
- USB ADB remains the recovery path during the USB-host conversion work. Once host mode is enabled, normal management should use Wi-Fi SSH. See `docs/uno-q-usb-camera.md` for the power, role-switch and verification procedure.
- Direct 5 V header power was tested with two USB cameras. The board and sensor app worked, but the Type-C port remained data-role `device`, power-role `sink`, with `usb_vbus` disabled. A forced DWC3 host mode exposed only the Linux root hubs and no camera attach event. The externally powered USB-C/PD hub is still required for the next camera test.

## Latest measurements

- KX134 read benchmark: 1,000 Z-axis reads in 15,218 us.
- Portable 60-position ensemble inference: about 25.7 ms (`inference_us`, parity case on UNO Q).
- New TFLite candidates on UNO Q: CPU dynamic MLP / XNNPACK p95 1.84 ms end-to-end; GPU FP16 CNN / XNNPACK p95 2.57 ms; GPU FP16 CNN / Adreno 702 p95 16.94 ms. These are parity-input benchmarks and do not include sensor transfer or browser/audio latency.
- Cold WAV HTTP request: 73 ms in the latest check.
- Warm UNO-Q WAV cache request: 24 ms in the latest check. Normal performance preloads the WAV, so hit-time playback starts from a decoded browser `AudioBuffer` rather than waiting for HTTP or synthesis.
- Python syntax check and `test_uno_q*.py`: 12 tests passed.

## Remaining verification/work

1. With the acrylic panel attached, make one real strike and verify that the new `on_capture_chunk` callback completes one 512-sample event, inference advances exactly once, and sound plays once.
2. Measure strike-to-audio latency with a real strike. The remaining expected contributors are about 17.5 ms of post-trigger capture, the 115,200-baud MCU/Linux Bridge transfer, roughly 26 ms model inference, Wi-Fi/UI delivery, and the browser audio device buffer.
3. If transfer latency is still excessive, investigate a coordinated higher Bridge UART baud rate or a lower-overhead MCU/Linux transport. Do not change only the MCU baud; both ends must match.
4. Collect native KX134 training sessions over the full 400 x 300 panel, then retrain and validate the 12-area, 60-position probability/pseudo-XY, and direct-XY models on the PC when explicitly requested.
5. Compare predicted panel, maximum-probability panel, graph, and heat-map overlay against the new native KX134 validation set. They now share the same 60-position distribution, but accuracy still depends on native training data.
6. Connect the ordered externally powered USB-C hub and UVC camera, verify USB host negotiation and the port-4912 camera preview, then check the overlay alignment. Camera code is prepared but cannot be validated without that hardware.
7. Install the required UNO Q TFLite/LiteRT runtime, deploy the generated CPU dynamic and GPU FP16 candidates, and execute the parity/performance/camera-concurrency acceptance tests defined in `docs/uno-q-cpu-gpu-model-requirements.md`. Confirm from delegate logs that the GPU candidate is actually delegated rather than silently falling back to CPU.

## Resume checklist

1. Open `http://192.168.101.85:8765/instrument-probability.html` in the secondary environment (or use the current address reported by `hostname -I`) and perform a hard refresh if an older tab remains open.
2. After connecting the sensor, confirm `/api/status` reports `sensor_ready: true`, `sample_rate_hz: 25600`, and `missed_data_ready: 0` after startup.
3. Start performance, wait for note preloading to finish, then make one strike while watching the inference sequence and application log.
4. Preserve any files below the UNO Q app's `data/training` directory before doing device replacement or manual cleanup.
