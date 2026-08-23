# UNO Q 400 × 300 座標モデル・楽器モード

別リポジトリ `D:\GitHub\acrylic_pan` で2026-08-23 11:37に生成された最新モデルを、UNO QのLinux側で実行する。

## 使用モデル

- 元モデル: `artifacts/pc_position_runtime_400x300x5/position_ensemble.joblib`
- 実験名: `pc_position_400x300x5_grid_v7`
- パネル: 400 × 300 × 5 mm
- 学習データ: 11セッション、7,132波形
- 測定座標: 12中心 + 48四隅 = 60座標
- 入力: 25.6 kHz、512サンプル、トリガー位置64
- 特徴量: 時間448 + FFT256 + 統計10 = 714
- 構造: 714—384—192—96、3モデルアンサンブル
- 表示用モデル: 60クラス条件付き確率モデル、3モデルアンサンブル

元の33 MB joblibはscikit-learnの保存形式に依存するため、係数、バイアス、スケーラー、60座標、温度補正値をNumPy NPZへ移す。UNO Q上ではscikit-learnを使わず、NumPyで同じ前向き計算を行う。

## 検証値

共通holdoutにおける直接XYアンサンブル:

- 平均距離: 7.48 mm
- 中央値: 4.94 mm
- 90%点: 13.28 mm
- 25 mm以内: 96.97%

60座標確率モデル:

- Top-1座標一致率: 98.88%
- MAP平均距離: 1.13 mm
- 確率加重平均距離: 1.81 mm

四隅セッションをすべて学習に使用したため、完全未学習の外部セッション評価は残っていない。この制約は画面にも表示する。

## 画面

- 座標テスト: `http://<UNO-Q-IP>:8765/position.html`
- 楽器モード: `http://<UNO-Q-IP>:8765/instrument.html`
- 状態API: `http://<UNO-Q-IP>:8765/api/status`

座標画面は60座標の確率分布、最尤座標、確率加重平均、90%信用領域、100 mm角の12ゾーンを表示する。楽器画面は最尤座標から4 × 3ゾーンを決定し、12音へ割り当てる。

## モデルの取り込み

```powershell
D:\GitHub\acrylic_pan\.venv\Scripts\python.exe scripts/import-acrylic-pan-position-model.py
powershell -ExecutionPolicy Bypass -File scripts/deploy-uno-q-dummy.ps1
```

取り込み時に、元モデルと同じ60波形を両形式で推論するパリティケースも生成する。許容差は期待座標で0.0001 mm未満とする。

## 実センサー復旧後

`uno_q_app/sketch/sketch.ino` の `APAN_DUMMY_MODE` を `0` に変更する。KX134から受信した512サンプルを保存し、714特徴抽出、60座標確率推論、直接XY推論を順に行う。トリガー位置は学習契約に合わせて64サンプルとする。
