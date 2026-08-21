# Arduino UNO Q 移行方針

## 1. 目的

旧構成のパネル、KX134-1211、教師データ、信号処理、8クラス定義を維持しつつ、
ML63Q2557専用部分をUNO QのSTM32U585とQRB2210へ置き換える。

## 2. 責務の分割

| 処理 | 旧構成 | UNO Q構成 |
| --- | --- | --- |
| センサ取得 | ML63Q2557 | STM32U585 Arduino sketch |
| 打撃検出 | ML63Q2557 | STM32U585 Arduino sketch |
| 波形転送 | UARTF1 / COBS | Arduino Bridge（分割転送） |
| 収録 | Windows PC | QRB2210 Debian Python |
| 特徴抽出 | MCU / PC | 初期はQRB2210 Python |
| 推論 | Solist-AI / ML63Q2557 | QRB2210上のモデルへ移行 |
| UI・音源 | Windows PC | QRB2210 Web UI・音声出力へ移行 |

STM32U585は決定論的な取得だけに集中させる。BridgeやLinuxの遅延をサンプリング経路へ
持ち込まず、512点が揃ってから64点ずつ送信する。

## 3. 段階的な移行

### Phase 1: センサBring-up

- WHO_AM_Iが`0x46`であることを確認
- ±64 g、25.6 kHz設定を確認
- 無打撃時と単発打撃時の512点を保存
- 実効サンプル周期、欠落、ピーク飽和をロジックアナライザと保存データで評価

### Phase 2: 既存PC処理との整合

- UNO Q JSONLから既存NPZイベント形式への変換を追加
- `sim.solist_dataset` が同じ512点・25.6 kHzとして読み込めることを確認
- 旧ボードとUNO Qで同じ打撃を収録し、FFTと帯域特徴を比較

### Phase 3: Linux側推論

- 既存の8クラス教師データからONNX等の移植可能なモデルを生成
- QRB2210上で前処理、推論、期待座標を実行
- 推論レイテンシと分類精度を測定

### Phase 4: スタンドアロン化

- Web UIと音源をUNO Qへ移す
- App LabのRun at startupを有効化
- 必要に応じてBridge転送を特徴量だけに縮小

## 4. 確定したセンサー配線

- SPI2: D13=SCK、D12=CIPO/MISO、D11=COPI/MOSI、D10=CS
- 割り込み予約: D2=INT1、D3=INT2
- 電源: CN1-5/8を3.3 V、CN1-2/4/11/13をGND
- I2C用CN1-1/3は未接続
- 詳細: [`uno-q-sensor-wiring.md`](uno-q-sensor-wiring.md)

## 5. 実機で決める項目

- SPIクロックと信号品質
- `micros()`方式のジッタ許容可否
- 打撃しきい値（初期値: jerk 120、level 80 raw counts）
- Bridgeの連続通知で安全な最大チャンク長
- QRB2210側モデル形式と音声バックエンド

## 6. 旧ファームの扱い

`firmware/AcrylicPanCollector` と `firmware/variants` は移植の比較元として保持する。
UNO Q版がデータ収録・推論・UIまで置換できた時点で、`firmware/legacy_ml63q2557/`
への整理または別ブランチへの退避を検討する。
