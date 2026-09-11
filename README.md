# Acrylic Pan for Arduino UNO Q

400 x 300 x 5 mm のアクリルパネルを打楽器兼タッチインターフェースにする
Arduino UNO Q 向けプロジェクトです。MPU9250 加速度センサの振動波形から
4 x 3領域（12クラス）の打撃位置を推定し、音階とヒートマップへ変換します。
旧400 x 200 x 3 mm・4 x 2構成は比較用パネルプロファイルとして保持します。

このリポジトリは旧 `acrylic_pan` から履歴を引き継いだ移植プロジェクトです。
旧 ML63Q2557 / LEXIDE ファームは比較資料として `firmware/` に残し、新しい実装は
`uno_q_app/` に置きます。

AIモデルは旧ML63Q2557のRAM、ノード数、bfloat16、1隠れ層ELMの制約を継承しません。
旧モデルをbaselineとして残しつつ、UNO Qの計算能力に合わせた3軸時系列モデルと
multi-task推論で精度向上を狙います。詳しくは [開発方針](docs/development-policy.md) を参照してください。

元プロジェクトの実測7,132イベントをMPU9250相当へ変換し、12クラス、60クラス＋疑似XY、
直接XYモデルを再学習して `uno_q_app` に搭載しています。UNO Q内で実センサデータの採取、
再学習、推論、ヒートマップ・楽器画面の配信まで完結します。

## 現行MPU9250 App

```text
MPU9250 (4 kHz / ±16 g) --SPI--> STM32U585
                                  | 80点イベント検出
                                  v
                             Arduino Bridge
                                  v
                     QRB2210 / NumPyモデル・HTTP UI
```

UNO Qのポート8765から、推論結果 `/`、学習データ採取 `/collector.html`、位置推論
`/position.html`、クラス演奏 `/instrument.html`、60点確率演奏
`/instrument-probability.html` を配信します。実装・再学習手順は
[`uno_q_app/README.md`](uno_q_app/README.md) を参照してください。

USBカメラはPCではなくUNO QのLinux側で取得し、公式ビデオBrickがポート4912の
`/embed`から配信します。外部給電対応USB-Cハブ、給電方法、Wi-Fi管理への切替、
接続後の確認手順は[UNO Q USBカメラ構成](docs/uno-q-usb-camera.md)にまとめています。
USBホスト運転後の配備には `scripts/deploy-uno-q-wifi.ps1` を使用します。

### MPU9250実測データの扱い

`http://<UNO-Q-IP>:8765/collector.html` で採取したデータのPC保存、再学習、評価、
UNO Qへの配備はWeb UIから自動実行しません。指示を受けた段階で既存JSONLを保護し、
各処理を個別に実施します。詳細は [`uno_q_app/README.md`](uno_q_app/README.md) を
参照してください。

## センサなしUNO Q実機確認

KX134を接続する前は、元リポジトリの12クラスモデルと代表入力を使って
STM32 → Bridge → Linux推論を確認できます。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy-uno-q-dummy.ps1
```

STM32がcase 0〜11を通知し、QRB2210が128-32-12モデルを推論して
`data/inference/dummy_results.jsonl`へ保存します。手順と実機結果は
[UNO Qセンサなしダミー推論Bring-up](docs/uno-q-dummy-bringup.md) を参照してください。

### PC Web UI

UNO QをUSB接続し、ダミーAppを起動した状態で次を実行します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-uno-q-web.ps1
```

ブラウザで `http://127.0.0.1:8765/` が開き、ADB経由で取得した直近の推論結果を表示します。
12領域の打点マップ、各クラスのscore、判定一致率、推論時間、履歴を1秒ごとに更新します。
Web UIはPC上で動作し、UNO Q側へ追加パッケージを導入しません。

Wi-Fi接続中のUNO Q実機を操作しながら、PCカメラまたはUNO Q側USBカメラを選んで
確率ヒートマップを重畳する場合は次を実行します。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-dual-camera-ui.ps1
```

開いた確率演奏画面の「カメラ入力」で入力元を選択します。視点ごとの8点フィット（四隅4点と、
左右の縦辺上にある2本の行境界4点）は別々に保存されます。行境界は左右独立の縦辺比率として
調整できるため、斜め方向から撮影した4×3エリアの奥行き方向の縮みも補正できます。
UNO Q側カメラには外部給電対応USB-Cハブが必要です。

同じサーバーの `http://127.0.0.1:8765/docs`、またはダッシュボード右上の「設計資料」から
ドキュメントポータルを開けます。元リポジトリから継承した2D板、3Dソリッド、CalculiXの
シミュレーション結果に加え、現行BOMとKX134–UNO Qの全14ピン配線を表示します。

## UNO Qでの構成

```text
KX134-1211 --SPI--> STM32U585 (Zephyr/Arduino sketch)
                         |  25.6 kHz取得、打撃検出、512点切り出し
                         v
                    Arduino Bridge
                         |
                         v
                 QRB2210 (Debian/Python)
                         |  保存、特徴抽出、推論、Web UI、音源
                         v
                    ブラウザ / 音声出力
```

UNO Q App Lab実装は、現在 `APAN_DUMMY_MODE=1` でセンサアクセスを無効化しています。
ダミー経路の確認後に有効化する実センサ側コードは次を含みます。

- KX134-1211のSPI初期化とWHO_AM_I検査
- Z軸を25.6 kHz相当で読み取るMCU側サンプラ
- プリトリガ128点を含む512点の打撃イベント切り出し
- Bridgeの分割メッセージによるLinux側への波形転送
- Linux側でのJSONL保存

## 配線（確定）

| KX134-1211 | UNO Q |
| --- | --- |
| VDD / IO_VDD | 3.3 V |
| GND | GND |
| SCLK | SCK |
| SDI | COPI/MOSI |
| SDO | CIPO/MISO |
| nCS | D10 |

旧評価キットの14ピンIDCコネクタは、D10-D13のSPI、D2/D3の割り込み予約、
3.3 VおよびGNDへ展開します。KX134-1211は3.3 Vで使用し、UNO QのJSPIにある
5 V端子へは接続しません。全14ピンの配置、CN1の向き、変換アダプタ仕様は
Solist AI用KX134ブレークアウトボードは[`docs/uno-q-sensor-wiring.md`](docs/uno-q-sensor-wiring.md)、
KX132-1211-EVK-001は[`docs/kx132-1211-evk-wiring.md`](docs/kx132-1211-evk-wiring.md)を参照してください。

## 起動

1. Arduino App LabでUNO Qへ接続する。
2. `uno_q_app` をAppとして開く（またはUNO Qへコピーする）。
3. AppをRunする。
4. Appログで `KX134 ready` を確認する。
5. パネルを打撃し、`data/captures/events.jsonl` が生成されることを確認する。

実機で最初に確認すべき内容と旧実装との差分は
[`docs/uno-q-migration.md`](docs/uno-q-migration.md) にまとめています。

## PC側の既存資産

`pc/`、`sim/`、`calculix/`、`web/`、`tests/` は旧プロジェクトから継承しており、
データ形式と解析の移行が完了するまでそのまま利用できます。Pythonテストは次で実行します。

UNO Q実機向けのPC Web UIは `pc/uno_q_web/` にあります。旧UIを直接流用せず、
UNO QのADB接続と現在のJSONL結果形式に合わせた標準ライブラリのみの実装です。

```powershell
python -m pytest
```

## 現在の制約

- 25.6 kHz周期は現段階では `micros()` によるソフトウェアスケジューリングです。
  実機計測後、必要ならKX134のDRDY割り込みまたはFIFOへ切り替えます。
- Bridge転送中は次の打撃イベントを取得しません。
- Solist-AI固有モデルはUNO Qへ移植せず、Linux側推論へ置き換える予定です。
- App Lab/Zephyrでの実機ビルドとセンサ動作確認はUNO Q本体が必要です。
