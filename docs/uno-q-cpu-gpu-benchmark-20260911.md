# UNO Q CPU/GPUモデル実機評価

評価日: 2026-09-11

## 結論

今回生成した2種類の候補では、**GPU向けCNNをUNO QのCPU/XNNPACKで実行する構成**が、精度と遅延のバランスで最も良かった。

- CPU向けMLPは最速だが、別開発環境の全テストセットで60点精度がGPU向けCNNより低い。
- GPU向けCNNはCPU/XNNPACKでも前処理込みp95 2.57 msで動作し、48格子点×2件の実機parityセットでtop-1が100%一致した。
- 同じCNNをAdreno 702へ実委譲できたが、前処理込みp95は16.94 msだった。バッチ1の小型モデルでは、GPUの起動、データ転送、同期コストが演算短縮効果を上回った。
- 現モデル規模ではCPU/XNNPACKを採用候補とし、GPUはカメラ処理へ残す。モデルを大型化した場合は同じ方法で再測定する。

この評価だけで稼働中の演奏アプリは切り替えていない。現在の配備モデルは引き続き `acrylic_pan_position_400x300x5_grid_v7_portable` のNumPy CPU版である。

## 取り込んだ候補

Git commit `91f10cd` (`feat: train UNO Q CPU and GPU position models`) から次を評価した。

| 用途 | ファイル | 入力 | 概要 |
|---|---|---|---|
| CPU候補 | `acrylic_pan_xy_cpu_dynamic.tflite` | 714 float32特徴 | 動的範囲量子化MLP、約182 KB |
| GPU候補 | `acrylic_pan_xy_gpu_fp16.tflite` | 448 × 1 × 3 float32 | FP16重みCNN、約2.17 MB |

CPU候補は、448点の正規化時間波形、256 FFT bin、10統計量を入力する。GPU候補は、448点の正規化波形、log peak、log RMSの3チャンネルを入力し、4段のConv2Dと全結合headから60点確率と直接XYを出力する。

## 別開発環境での固定テストセット評価

`uno_q_model_candidates/*_model_metadata.json` に記録された1,907件のセッション分離テスト結果を比較した。このテストセッションと実機parityは四隅側48格子点を対象としており、12中心点を含まない。出力層は60クラスだが、この表を全60点の外部セッション精度とは扱わない。

| 指標 | CPU dynamic MLP | GPU FP16 CNN |
|---|---:|---:|
| 60点top-1 | 96.70% | 97.95% |
| 12エリア精度 | 98.69% | 98.85% |
| MAP XY平均距離 | 2.73 mm | 1.91 mm |
| Expected XY平均距離 | 3.34 mm | 1.86 mm |
| Direct XY平均距離 | 31.64 mm | 14.00 mm |
| ECE | 0.0102 | 0.0093 |

CNNは60点確率、期待値座標、直接回帰のすべてでMLPより良かった。ただし直接回帰は確率分布から求めるMAP/expected XYより誤差が大きいため、現時点の表示・演奏判定は60点確率を主結果として扱う。

## UNO Q実機測定

測定条件:

- QRB2210 / Adreno 702
- Python 3.13.9
- `ai-edge-litert 2.2.0`
- CPUは4 thread XNNPACK
- GPUはArduino公式 `ei-models-runner:0.5.0` に含まれる `libtensorflowlite_gpu_delegate.so`
- OpenCLはMesa/Rusticl、`RUSTICL_ENABLE=freedreno`
- parity 96件（四隅側48格子点を各2件。12中心点は含まれない）を10周
- 時間はモデル呼出し直前・直後を計測。初期化とウォームアップ10件は統計から除外

| モデル／実行先 | 推論p50 | 推論p95 | 前処理p95 | 前処理込みp95 | 96件top-1 |
|---|---:|---:|---:|---:|---:|
| CPU dynamic MLP／CPU XNNPACK | 0.36 ms | 0.43 ms | 1.44 ms | 1.84 ms | 97.92% |
| GPU FP16 CNN／CPU XNNPACK | 1.43 ms | 1.78 ms | 0.77 ms | 2.57 ms | 100% |
| GPU FP16 CNN／Adreno 702 | 14.56 ms | 16.00 ms | 1.48 ms | 16.94 ms | 100% |

GPU測定時のログは次を確認した。

```text
INFO: Initialized OpenCL-based API.
INFO: Created 1 GPU delegate kernels.
```

したがってGPU値はCPU fallbackではない。モデル全体は一つのdelegate nodeとして実行された。

### 評価範囲の制約

要件では全60点を含むparityセットを求めていたが、受領ファイルのラベルを検査すると、含まれていたのは48ラベルで各2件だった。中心12点の別セッション性能は今回のUNO Q照合では確認できていない。モデル再検討時には、中心12点を含む固定テストセットとparityセットを追加し、中心と四隅を分けた指標も出すこと。

## 解釈

CPU候補は714入力の小型全結合モデルで、XNNPACKが得意な処理である。GPU候補も約2.17 MBと小さく、入力は1イベントだけなので、CPUではキャッシュとNEON/XNNPACKで短時間に処理できる。一方GPU実行ではOpenCL command、テンソル転送、同期の固定費が毎回発生する。演算量がその固定費を償却できないため、Adreno 702を使った方が遅くなった。

GPU向けに設計したCNNであっても、TFLiteの対応演算だけで構成されているためCPU/XNNPACKで正常に実行できる。モデル構造の名称と、実際の実行バックエンドは別に判断する必要がある。

## 再検討時の方針

次回モデルでは、以下の候補を同じ固定テストセットと実機スクリプトで比較する。

1. 現GPU CNN相当の精度を維持しつつ、CPU/XNNPACK向けにチャンネル数や全結合層を削減したCNN。
2. 直接XY headの損失重み・教師表現を見直し、確率MAP/expected XYとの差を縮めたmulti-task CNN。
3. GPU利用を前提に十分な演算密度を持たせた大型CNN。ただしカメラとのGPU競合も測る。
4. 単発batch 1だけでなく、将来複数センサや画像特徴を同時処理する場合のbatch／fusionモデル。

GPU候補は「GPUで動いた」ことだけで採用しない。CPU版より高精度になる、CPU負荷を大きく解放する、または大型化後にp95遅延がCPUを下回る場合に採用する。

## 再現方法

実機測定スクリプトは `scripts/benchmark_uno_q_tflite.py` を使用する。CPU測定ではdelegateを指定せず、GPU測定では `--delegate` にGPU delegate共有ライブラリを指定する。GPU実行時は `RUSTICL_ENABLE=freedreno` を設定し、ログにGPU kernel生成が出たことを確認する。

今回の`pip`とOpenCLパッケージ導入は、稼働中のアプリコンテナ内で行った評価用の一時設定である。アプリ再配備時に消えるため、正式採用時はLiteRT、GPU delegate、OpenCL依存関係を再現可能なBrickまたはコンテナ構成として固定する。
