# UNO Q CPU/GPU model candidates

Generated with `scripts/train_uno_q_cpu_gpu_models.py`. The selected CPU candidate is `acrylic_pan_xy_cpu_dynamic.tflite`; the selected GPU candidate is `acrylic_pan_xy_gpu_fp16.tflite`. INT8 is retained for diagnosis but rejected because its held-out accuracy and parity are worse. GPU delegate execution and latency must be verified on the UNO Q before deployment. See `evaluation_report.json` for all metrics.
