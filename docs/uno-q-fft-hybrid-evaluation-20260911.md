# UNO Q embedded-FFT hybrid model evaluation

Evaluation updated: 2026-09-12

## Conclusion

The dataset was split by complete recording session with no event leakage. Unlike the earlier comparison, the training, validation, and held-out test splits now each contain all 60 positions, including the 12 center positions. The held-out test has 2,507 strikes.

The large embedded-FFT FP16 model is selected. It accepts a raw 512-sample waveform and performs baseline removal, amplitude normalization, a Hann-windowed RFFT, and time/frequency fusion inside TFLite. It achieved 97.05% 60-position top-1 accuracy, 99.44% 12-area accuracy, 1.78 mm MAP mean error, and 1.76 mm probability-weighted expected-XY mean error.

| Model | Parameters | FP16 size | 60-position top-1 | 12-area | MAP mean | Expected XY mean |
|---|---:|---:|---:|---:|---:|---:|
| Temporal CNN | about 1.08 M | 2.17 MB | 95.45% | 99.36% | 2.63 mm | 2.73 mm |
| FFT hybrid standard | 1.68 M | 3.38 MB | 96.77% | 99.20% | 2.13 mm | 2.70 mm |
| **FFT hybrid large** | **5.90 M** | **11.82 MB** | **97.05%** | **99.44%** | **1.78 mm** | **1.76 mm** |
| Temporal + large FFT ensemble | 6.98 M | 14.01 MB | 97.01% | 99.44% | 1.89 mm | 1.86 mm |

The validation-selected ensemble used 10% temporal CNN and 90% large FFT, but it was slightly worse than the large FFT model alone on held-out top-1 and coordinate error. The simpler large FFT model is therefore the deployment candidate.

## Evaluation split

- Total: 11 sessions, 7,132 strikes
- Training: 7 sessions, 3,545 strikes, all 60 positions
- Validation: 2 sessions, 1,080 strikes, all 60 positions
- Held-out test: 2 sessions, 2,507 strikes, all 60 positions
- Split unit: complete recording session
- Model selection and ensemble weighting: validation only
- Final reported metrics: held-out test only

This removes the earlier 48-of-60 test limitation. Center-position recordings are not copied into the corner sessions; one center session and one corner session are assigned together to each of validation and test, preserving session independence while providing complete positional coverage.

## Model contract

- Input: 512 raw ADC samples, float32
- Temporal branch: 448 post-baseline samples through four Conv2D blocks
- Frequency branch: Hann-windowed RFFT, excluding DC, using 256 log-magnitude bins
- Auxiliary features: log peak, log RMS, and peak/RMS
- Outputs: 60-position probability distribution and normalized direct XY
- Selected quantization: FP16 weights
- Selected artifact: `acrylic_pan_fft_hybrid_large_fp16.tflite`
- TFLite operators include `RFFT2D` and `COMPLEX_ABS`

UNO Q device latency should be re-measured with `scripts/benchmark_uno_q_tflite.py --variant fft-hybrid` after deploying the new 11.82 MB model. The previous standard-model timing is not used as a claim for the new large model.
