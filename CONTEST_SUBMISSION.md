# Hackster contest submission checklist

This checklist keeps the public article, repository, and demonstrated UNO Q system consistent.

## Ready

- [x] Clear project name and one-sentence value proposition
- [x] Arduino UNO Q is the complete application host
- [x] KX134-1211 3.3 V SPI wiring and connector orientation documented
- [x] Complete BOM documented
- [x] Simulation GIF showing position-dependent vibration modes
- [x] System architecture diagram
- [x] One-sensor-to-60-position AI diagram
- [x] Low-latency processing diagram
- [x] 60-anchor training layout
- [x] Complete-session evaluation split covering all 60 positions
- [x] Selected embedded-FFT FP16 model and reproducible report
- [x] Source, firmware, App Lab application, models, tests, and documentation in the repository
- [x] GeneralUser GS notice and credit included
- [x] Japanese Story review page

## Capture before final publication

- [x] Replace the overview placeholder with a photograph of the complete instrument (`device-overview.jpg`)
- [x] Add close-up photographs of the keyed cable and mounted KX134 (`kx134-sensor-top.jpg`, `kx134-sensor-bottom.jpg`)
- [x] Add UNO Q / USB-C hub and mallet photographs (`arduino-uno-q.jpg`, `mallet-overview.jpg`, `mallet-tip.jpg`)
- [ ] Add a collector-page screenshot showing one clean 512-sample waveform
- [x] Add a performance-page screenshot with the heat map aligned to the acrylic panel (`probability-instrument-ui.png`; retake with the large FFT model selected and the stream URL hidden if possible)
- [ ] Record one continuous end-to-end demo video with visible strikes, matching overlay, and audible notes
- [ ] Avoid faces, unrelated workbench clutter, passwords, IP addresses, and private network names in screenshots

## Verify on the contest UNO Q

- [ ] Deploy `acrylic_pan_fft_hybrid_large_fp16.tflite`
- [ ] Confirm `WHO_AM_I = 0x46`, `sensor_ready = true`, 25.6 kHz, and zero missed sample periods
- [ ] Measure warm inference latency of the selected 11.82 MB large FFT model
- [ ] Measure strike-to-sound latency with the camera and audio services running
- [ ] Confirm the probability graph, winning panel, area result, coordinate, and camera heat map agree
- [ ] Power-cycle UNO Q and confirm acquisition, inference, camera, audio, and web services start automatically

## Hackster editor

- [ ] Update the Story dataset split to 3,545 train / 1,080 validation / 2,507 held-out test
- [ ] State explicitly that every split covers all 60 positions, including the 12 centers
- [ ] Update selected-model metrics to 97.05% position, 99.44% area, 1.78 mm MAP, and 1.76 mm expected XY
- [ ] Do not apply old UNO Q timing measurements to the new large model before measuring it
- [ ] Upload the PNG figures at the locations in `docs/hackster-story-media-plan.md`
- [ ] Add source, schematics, trained model, and demo media under Attachments
- [ ] Confirm the public Story does not describe the project as a port or migration
- [ ] Review the complete English article once in the published-width preview

## Repository release check

- [ ] Choose and add a top-level project license
- [ ] Run `python -m unittest discover -s tests -p "test_uno_q*.py"`
- [ ] Run `git diff --check`
- [ ] Confirm no Wi-Fi passwords, SSH keys, tokens, or private captures are tracked
- [ ] Commit and push the final contest revision
