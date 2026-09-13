# UNO Q embedded-FFT hybrid candidates

These candidates accept one raw 512-sample waveform and perform baseline removal, normalization, Hann-windowed RFFT, time-domain convolution, and time/frequency fusion inside the TFLite model. The selected artifact is `acrylic_pan_fft_hybrid_large_fp16.tflite`. See `evaluation_report.json` for held-out metrics on the whole-session split covering all 60 positions.
