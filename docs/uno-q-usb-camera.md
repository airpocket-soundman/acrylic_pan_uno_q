# UNO Q USB camera and host-mode setup

Last updated: 2026-09-11 (JST)

## Decision

The USB camera is owned by the UNO Q Linux MPU, not by the PC browser and not by the STM32 MCU sketch. The MCU remains dedicated to deterministic 25.6 kHz KX134 acquisition. The official UNO Q video brick opens the UVC camera and publishes its preview from port 4912; the Acrylic Pan Web UI embeds `http://<UNO-Q-address>:4912/embed` and draws the impact-probability overlay above it.

The probability-instrument screen supports two selectable camera inputs:

- **This PC camera** uses the browser camera API and overlays the same 60-position heatmap locally in the browser.
- **UNO Q USB camera** embeds the UNO Q stream from port 4912 and overlays the heatmap in the same browser view.

Each source stores its own eight-point panel alignment because the viewpoints can differ. The first four points define the panel corners. The other four define the left and right endpoints of the two horizontal row dividers as independent ratios along each vertical edge. This corrects the apparent row-height change caused by perspective and warps the grid, hit-area highlights, labels and probability heatmap together. To use the PC camera while controlling the UNO Q over Wi-Fi, launch the localhost SSH tunnel:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-dual-camera-ui.ps1
```

This opens `http://127.0.0.1:8765/instrument-probability.html`. The localhost address is required for direct browser camera access on a non-HTTPS development setup. Select the camera input on the page, press **Start camera**, and run eight-point alignment for that source. Afterward, blue corner points and orange row-divider points can all be dragged for fine adjustment; the divider labels show their left/right edge ratios.

The app declares the official `arduino:video_object_detection` brick with the `face-detection` model. This supplies the board-local camera pipeline and leaves a path for later visual inference. Acrylic Pan position inference remains independent from the camera model.

## Power and physical connection

Preferred final connection:

1. Connect a USB-C hub with external power delivery to the UNO Q USB-C connector.
2. Use a regulated 5 V / 3 A supply for the powered hub, as recommended by the UNO Q camera example.
3. Connect the UVC USB camera to the hub.
4. Manage the UNO Q over Wi-Fi SSH; do not depend on USB ADB while the port is hosting the camera.

Temporary board-only power is allowed through either of these official inputs:

- Regulated 5 V at up to 3 A into the JANALOG `5V` and `GND` pins.
- 7–24 V DC into `VIN` and `GND`; 12 V is suitable. Size the source with margin for the board, but do not assume VIN alone will supply or negotiate USB-camera power.

Never put 5 V into `VIN`, `3V3`, `IOREF`, or a GPIO. The JANALOG `5V` pin shares the USB 5 V power net, so do not connect a PC USB power source at the same time as a separate 5 V source on that pin.

## Switching from development-device mode

1. Confirm Wi-Fi access with `ssh arduino@<UNO-Q-address>`.
2. Stop writes and disconnect the PC USB-C cable.
3. Apply the selected external power source.
4. Connect the externally powered USB-C hub and camera.
5. Wait for the board to boot, then reconnect over Wi-Fi.

The USB-C controller normally changes role through Type-C negotiation. Do not install a debugfs role-forcing workaround unless the current OS fails this test; the installed image reports build `20251107-424`, newer than the early images for which the workaround was published.

## Secondary-environment direct-power test (2026-09-11)

A regulated 5 V source connected to the JANALOG `5V` and `GND` pins powered the UNO Q and the Acrylic Pan application correctly. However, with two different USB cameras tested at the USB-C connector, Linux still reported the Type-C port as data-role `device`, power-role `sink`, and `usb_vbus` disabled. Forcing only the DWC3 controller into host mode created the USB 2.0 and USB 3.0 root hubs, but neither camera produced a USB attach event, appeared in `lsusb`, or created a UVC capture node.

This result shows that powering the board through the 5 V header does not, by itself, complete USB-C host-role negotiation or provide a usable camera connection in the tested cable/adapter arrangement. Do not treat a software-created root hub as proof that camera VBUS is present. Continue with the ordered externally powered USB-C/PD hub; it must provide the correct Type-C role/CC connection as well as adequate power.

## Verification after the hub and camera arrive

Run these commands on the UNO Q over Wi-Fi:

```sh
cat /sys/class/typec/port0/data_role
cat /sys/class/typec/port0/power_role
lsusb
v4l2-ctl --list-devices
```

Expected results:

- `data_role` selects `host`.
- The camera appears in `lsusb`.
- A camera capture node appears in addition to the built-in Qualcomm Venus codec nodes. Do not select `/dev/video0` or `/dev/video1` merely by number without checking its device name; on the current image those two nodes are the Venus encoder and decoder.
- The app starts, port 8765 serves the Acrylic Pan UI, and port 4912 serves `/embed`.

Then verify:

```sh
curl -I http://127.0.0.1:4912/embed
curl http://127.0.0.1:8765/api/status
```

Finally open `http://<UNO-Q-address>:8765/instrument-probability.html`, confirm the camera image, perform the eight-point panel alignment, and make one real strike.

Once the camera is visible, deploy the prepared application without USB ADB:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-uno-q-wifi.ps1
```

The script verifies Wi-Fi SSH and a UVC camera before stopping the current app. It copies the application without deleting the remote `data` directory, provisions the official video brick, uploads the STM32 sketch, and waits for startup to finish.

## References

- [Arduino UNO Q product documentation](https://docs.arduino.cc/hardware/uno-q/)
- [Arduino UNO Q datasheet](https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf)
- The installed App Lab example `video-face-detection`, whose README specifies Network Mode, an externally powered USB-C hub, a USB camera, and a 5 V / 3 A hub supply.
