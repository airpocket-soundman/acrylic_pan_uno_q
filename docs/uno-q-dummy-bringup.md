# UNO Q センサなしダミー推論 Bring-up

最終更新: 2026-08-21

## 目的

KX134-1211を接続する前に、UNO QのSTM32U585、Arduino Bridge、QRB2210/Linux、
既存ダミーモデル、結果保存までの経路を実機で確認する。

このモードは物理センサ波形の精度を示すものではない。STM32からケース番号を1秒ごとに送り、
Linux側が `data/dummy_model/model.npz` とgolden inputを使って8クラス推論する自己診断である。

## 実装

- `uno_q_app/sketch/sketch.ino`: `APAN_DUMMY_MODE=1`でKX134を完全にbypassし、
  10秒のBridge warm-up後にcase 0〜7を循環通知する。
- `uno_q_app/python/dummy_model.py`: NumPyを使わずNPZ/NPYを読み、128-32-8 ELMを実行する。
- `uno_q_app/python/main.py`: Bridge通知を受け、期待値、推論値、8 score、推論時間をJSONL保存する。
- `scripts/deploy-uno-q-dummy.ps1`: 既存モデルを一時stagingへ同梱し、ADB経由で作成・更新・起動する。

モデルとgolden dataは配置時に `data/dummy_model` からコピーする。`uno_q_app` 内へ複製して
二重管理しない。

## 配置

WindowsではADBが `TMPDIR=/data/local/tmp` を注入するが、UNO QのDebianにはこのpathが
存在しない。そのためApp CLI起動時は `env -u TMPDIR` を使用する。

```powershell
winget install --id Google.PlatformTools --exact
powershell -ExecutionPolicy Bypass -File scripts/deploy-uno-q-dummy.ps1
```

ログ確認:

```powershell
adb shell env -u TMPDIR arduino-app-cli app logs /home/arduino/ArduinoApps/acrylic-pan-dummy
```

結果はコンテナ内の `/app/data/inference/dummy_results.jsonl` に保存される。

## PC Web UI

ダミーAppの起動後、PC側で次を実行する。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run-uno-q-web.ps1
```

`http://127.0.0.1:8765/` が開き、USB ADBでコンテナ内のJSONL末尾を読み取って表示する。
表示項目は接続状態、4 x 2打点マップ、8クラスscore、判定数、一致率、推論時間、直近履歴である。
センサ未接続時の値は自己診断用ダミー入力によるもので、実測精度を示さない。

Web UIを自動で開かない場合:

```powershell
python -m pc.uno_q_web --no-browser --port 8765
```

## 2026-08-21 実機結果

| 項目 | 結果 |
|---|---|
| USB device | VID 2341 / PID 0078、ADB接続成功 |
| UNO Q OS | Debian 13、aarch64 |
| Arduino App CLI | 0.8.2 |
| Zephyr Core | 0.53.1 |
| STM32 sketch | 17,732 bytes、global 5,364 bytes |
| App status | started |
| Bridge | case 0〜7を連続受信、再実装後のrouter errorなし |
| 分類 | 8/8一致、継続cycleでも一致 |
| 推論時間 | 初回約5.6 ms、観測した定常値は概ね7.3〜10.2 ms |
| PC Web UI | USB ADBから96件取得、100%一致表示、手動・自動更新成功 |
| センサ | 未接続、アクセスなし |

推論はQRB2210上のCPythonによるfloat演算である。旧ML63Q2557のbfloat16結果とのbit一致は
要件にせず、現段階ではclass一致をself-testの合格条件とする。

## センサ接続前に維持する条件

- `APAN_DUMMY_MODE` を1のままにする。
- KX134用GPIOへ電気的アクセスしない。
- ダミー結果をAcrylic Pan実測精度として扱わない。
- センサ接続時は配線導通と電圧を確認後、別commitで実センサbuildへ切り替える。
