# UNO Q embedded-FFT hybrid candidates

These candidates accept one raw 512-sample waveform and perform baseline removal, normalization, Hann-windowed RFFT, time-domain convolution, and time/frequency fusion inside TFLite. `acrylic_pan_temporal_fft_ensemble_fp16.tflite` is the validation-weighted primary candidate (85% temporal CNN, 15% FFT hybrid). The standard hybrid is retained as the smaller FFT-only candidate; the large hybrid is retained as a rejected size-scaling experiment. See `evaluation_report.json` for metrics and the important 48-of-60-position evaluation limitation.
