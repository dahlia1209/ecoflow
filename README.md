# EcoFlow Monitor

EcoFlow RIVER 2 Pro のデータを定期取得し、Azure Blob Storage にアップロードして Web ダッシュボードで可視化するシステムです。

## 機能

- EcoFlow Open Platform API 経由でデバイスデータを1分ごとに取得
- ローカルに JSON Lines 形式でログを記録（`logs/ecoflow.jsonl`）
- Azure Blob Storage へ15分ごとに差分アップロード
- Web ダッシュボードでバッテリー残量・出力・ソーラー入力をリアルタイム監視
- systemd サービスによる自動起動・常時稼働

## ハードウェア要件

- Raspberry Pi 4
- EcoFlow RIVER 2 Pro（またはその他の EcoFlow 対応デバイス）

## プロジェクト構成

```
ecoflow/
├── .env                          # 環境変数（要作成）
├── .gitignore
├── README.md
├── ecoflow_api.py                # EcoFlow HTTP API クライアント
├── ecoflow_logger.py             # 定期データ取得ロガー
├── upload_ecoflow_log.py         # Azure Blob Storage アップローダー
├── ecoflow-logger.service        # systemd サービスファイル
├── html/
│   └── index.html                # Web ダッシュボード
├── scripts/
│   └── upload_ecoflow_log.sh     # アップロード用シェルスクリプト
└── logs/                         # ログ保存ディレクトリ（自動生成）
    ├── ecoflow.jsonl             # デバイスデータログ（自動生成）
    └── service.log               # systemd サービスログ（自動生成）
```

## セットアップ

### 1. リポジトリのクローン

```bash
cd ~/src
git clone https://github.com/dahlia1209/ecoflow.git
cd ecoflow
```

### 2. 仮想環境の作成

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. パッケージのインストール

```bash
pip install requests python-dotenv azure-storage-blob
```

### 4. 環境変数の設定

`.env` ファイルを作成して以下の値を設定します。

```env
# EcoFlow API キー（IoT プラットフォームから取得）
ACCESS_KEY=your_access_key
SECRET_KEY=your_secret_key

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_BLOB_CONTAINER_NAME=root
ECOFLOW_BLOB_NAME=ecoflow-data/ecoflow.jsonl
```

EcoFlow の API キーは [EcoFlow Developer Platform](https://developer-eu.ecoflow.com) から取得してください。

### 5. 動作確認

```bash
# デバイス一覧の取得テスト
python3 ecoflow_api.py

# ロガーの手動起動テスト
python3 ecoflow_logger.py
```

## systemd サービスの設定

### サービスファイルの配置

```bash
sudo cp ecoflow-logger.service /etc/systemd/system/
```

### サービスの有効化と起動

```bash
sudo systemctl daemon-reload
sudo systemctl enable ecoflow-logger   # 再起動後も自動起動
sudo systemctl start ecoflow-logger
sudo systemctl status ecoflow-logger
```

### サービス管理コマンド

```bash
# 停止
sudo systemctl stop ecoflow-logger

# 再起動
sudo systemctl restart ecoflow-logger

# ログのリアルタイム確認
tail -f ~/src/ecoflow/logs/service.log
```

> ⚠️ `sudo python3` で直接実行すると `service.log` が root 所有になり、次回サービス起動時にログ書き込みが失敗します。必ず `sudo systemctl` 経由で操作してください。

## Azure へのアップロード設定

### スクリプトに実行権限を付与

```bash
chmod +x ~/src/ecoflow/scripts/upload_ecoflow_log.sh
```

### 手動アップロード

```bash
python3 upload_ecoflow_log.py
```

### cron で15分ごとに自動アップロード

```bash
crontab -e
```

以下の行を追加します。

```cron
*/15 * * * * /home/dahlia1209/src/ecoflow/scripts/upload_ecoflow_log.sh
```

設定を確認します。

```bash
crontab -l
```

## ダッシュボード

`html/index.html` を Azure Blob Storage にアップロードすることで Web ダッシュボードを公開できます。

ダッシュボードの機能は以下の通りです。

- バッテリー残量（SOC）・総出力・ソーラー入力の現在値カード
- バッテリー残量・出力・ソーラー入力の推移グラフ
- 1h / 6h / 24h / 3d / 7d / 30d のプリセット期間選択
- カスタム日時範囲の指定
- 5分ごとの自動更新

## データフォーマット

`logs/ecoflow.jsonl` に1分ごとに1行追記されます（JSON Lines 形式）。

```json
{"timestamp": "2026-03-28T10:00:00+00:00", "sn": "R621ZJ16XH4M1337", "data": {"pd.soc": 86, "pd.wattsOutSum": 81, "mppt.inWatts": 0, ...}}
{"timestamp": "2026-03-28T10:01:00+00:00", "sn": "R621ZJ16XH4M1337", "data": {"pd.soc": 85, "pd.wattsOutSum": 82, "mppt.inWatts": 0, ...}}
```

主なデータフィールドは以下の通りです。

| フィールド | 説明 |
|---|---|
| `pd.soc` | バッテリー残量（%）|
| `pd.wattsOutSum` | 総出力（W）|
| `inv.outputWatts` | AC 出力（W）|
| `mppt.inWatts` | ソーラー入力（W）|
| `bms_emsStatus.dsgRemainTime` | 放電残り時間（分）|

## 参考

- [EcoFlow Developer Platform](https://developer-eu.ecoflow.com/us/document/introduction)
- [Azure Blob Storage ドキュメント](https://learn.microsoft.com/ja-jp/azure/storage/blobs/)