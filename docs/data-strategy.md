# 学習データの移行・追加収録・管理方針

最終更新: 2026-08-21

## 現在のデータ状況

旧 `acrylic_pan` リポジトリには `data/dummy_model` のダミー／合成データだけがあり、
Acrylic Pan の実測学習データは含まれていない。一方、元プロジェクトを開発したPCには
実測元データが残っており、これを初期学習データセットとして流用する。

現在の作業PCは元プロジェクトの開発PCではないため、元データの取得、内容確認、変換、学習は
この環境ではまだ実行できない。データ移行までの間は、コネクタとGPIO、KX134収録基盤、
現行schema、データ受入ツール、モデルの入出力、評価コードと手順を先に整備する。

このPCにある `IchiPing` / `IchiPing_solist_AI` のデータは別案件であり、Acrylic Pan の
初期教師データには使用しない。

## 元開発PCからの移行手順

1. 元データの場所、所有者、作成日時、容量、当時の収録コード版を inventory に記録する。
2. 原本を変更せずに複製し、ファイルごとの SHA-256 を記録する。
3. センサ、軸、単位、ODR、レンジ、LPF、窓長を確認する。
4. 打点の座標系、class ID、板寸法、センサ位置、固定方法を確認する。
5. 欠損、飽和、重複、ラベル矛盾、時系列長を自動検査する。
6. 変換スクリプトで現行 session 形式へコピーし、変換前後の対応表を残す。
7. 可視化とbaselineでラベルの妥当性を人が確認する。
8. dataset version を付けて初めて学習対象へ昇格する。

## 移行待ちの間に進める作業

- 独自コネクタのピン配置と UNO Q GPIO 対応の確定
- STM32U585によるKX134の3軸SPI取得、リングバッファ、Bridge転送
- `session.json`、`manifest.jsonl`、`events/*.npz` のschemaとvalidator
- 旧データ向けimporterのインターフェースと受入レポート形式
- 旧ELM、1D CNN / TCN、spectrogram CNNの共通dataset API
- group split、評価指標、model card、UNO Q latency benchmarkの枠組み
- 追加収録が必要な条件の収録計画

## 現行の保存単位

```text
data/raw/sessions/<session-id>/
  session.json
  manifest.jsonl
  manifest.csv
  events/*.npz
```

大容量の原波形は Git へ直接 commit しない。リポジトリにはschema、manifest、hash、収録・
変換スクリプト、少数のtest fixtureを置く。実データの保管先を決めたら、アクセス方法と
dataset versionをREADMEに記載する。

## 分割とリーク防止

- 同一打撃の派生窓を複数splitに入れない。
- 同じ連打列、収録session、同じ日のデータをsplit間で混ぜない。
- 最低でも日またはsession単位でgroup splitする。
- データが不足する条件はUNO Qで追加収録し、打撃者とセンサ再取付けもhold-outにする。
- 正規化、特徴選択、augmentationの統計はtrain splitだけから算出する。
- test splitは最終候補の確定後に評価し、反復調整には使わない。

## 最低メタデータ

- board ID、センサ ID、ファーム version、配線／変換基板 version
- 板の材質・寸法・固定条件、センサ座標と軸方向
- sample rate、range、LPF、イベント長、trigger条件
- 打点XY、領域、強度または打撃治具条件、打撃者、時刻
- saturation、weak hit、multiple peak、overrun等の品質flag

## データ利用区分

| 区分 | 用途 | 精度主張への利用 |
|---|---|---|
| 元開発PCの実測・受入済み | 初期学習、検証 | 可 |
| 元開発PCの実測・未検証 | 棚卸しと品質確認 | 不可 |
| UNO Q + KX134追加実測・受入済み | 条件補完、検証、最終評価 | 可 |
| FEM／ダミー合成 | 実装、shape、数値安定性のtest | 不可 |
| IchiPing等の別案件 | 参考のみ | 不可 |
