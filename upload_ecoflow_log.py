"""
EcoFlow ログ → Azure Blob Storage アップローダー
sensor プロジェクトの upload_sensor_log.py と同仕様:
  - Append Blob への差分アップロード
  - .position ファイルで前回位置を管理
  - ローテーション検知（ファイルサイズが縮小したら先頭から再送）
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContentSettings
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  設定（環境変数で上書き可能）
# ─────────────────────────────────────────────
LOG_FILE         = Path(os.getenv("ECOFLOW_LOG_FILE", "logs/ecoflow.jsonl"))
CONTAINER_NAME   = os.getenv("AZURE_BLOB_CONTAINER_NAME", "ecoflow-logs")
BLOB_NAME        = os.getenv("ECOFLOW_BLOB_NAME",         "ecoflow-data/ecoflow.jsonl")
MAX_APPEND_BYTES = 4 * 1024 * 1024   # Azure Append Blob の1回上限 4MB

# ─────────────────────────────────────────────
#  ロギング
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Azure 接続マネージャー（シングルトン）
# ─────────────────────────────────────────────
class BlobConnectionManager:
    _instance: Optional["BlobConnectionManager"] = None
    client: Optional[BlobServiceClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            if not conn_str:
                raise ValueError(
                    "環境変数 AZURE_STORAGE_CONNECTION_STRING が設定されていません"
                )
            cls.client = BlobServiceClient.from_connection_string(conn_str)
        return cls._instance


# ─────────────────────────────────────────────
#  差分アップロード
# ─────────────────────────────────────────────

def upload_log_file(log_path: Path = LOG_FILE) -> bool:
    """
    ecoflow.jsonl を Append Blob に差分アップロードする。

    Args:
        log_path: アップロード対象のログファイルパス（デフォルト: LOG_FILE）
    Returns:
        成功時 True
    """
    temp_file: Optional[Path] = None
    try:
        if not log_path.exists():
            logger.warning("ログファイルが存在しません: %s", log_path)
            return False

        # ─ 前回アップロード位置を読み込む ─
        position_file = log_path.parent / f".{log_path.name}.position"
        last_position = 0
        last_mtime: Optional[int] = None

        if position_file.exists():
            try:
                with position_file.open() as f:
                    data = json.load(f)
                last_position = data.get("last_position", 0)
                last_mtime    = data.get("last_mtime")
            except Exception as e:
                logger.warning("position ファイル読み込み失敗（先頭から再送）: %s", e)
                last_position = 0

        # ─ ロック回避のため一時コピー ─
        temp_file = log_path.with_suffix(".tmp")
        shutil.copy2(log_path, temp_file)

        file_size     = temp_file.stat().st_size
        current_mtime = int(log_path.stat().st_mtime)

        # ─ ファイルサイズ縮小検知（手動でファイルを削除・リセットした場合） ─
        if file_size < last_position:
            if last_mtime is None or current_mtime > last_mtime:
                logger.info("ファイルリセットを検知。先頭から再送します")
                last_position = 0
            else:
                logger.warning("ファイルサイズ縮小かつ mtime 変化なし。スキップします")
                return True

        if file_size == last_position:
            logger.info("新規データなし: %s", log_path.name)
            return True

        # ─ 差分を読み込む ─
        with temp_file.open("rb") as f:
            f.seek(last_position)
            new_content = f.read()

        new_size = len(new_content)
        if new_size > MAX_APPEND_BYTES:
            logger.warning(
                "差分サイズが大きいです: %d bytes (上限 %d bytes)",
                new_size, MAX_APPEND_BYTES,
            )

        # ─ Blob へ追記 ─
        manager     = BlobConnectionManager()
        blob_client = manager.client.get_blob_client(
            container=CONTAINER_NAME, blob=BLOB_NAME
        )

        try:
            blob_client.get_blob_properties()
            logger.info("既存 Append Blob に追記: %s/%s", CONTAINER_NAME, BLOB_NAME)
        except Exception:
            logger.info("新規 Append Blob を作成: %s/%s", CONTAINER_NAME, BLOB_NAME)
            blob_client.create_append_blob(
                content_settings=ContentSettings(
                    content_type="application/x-ndjson; charset=utf-8"
                )
            )

        logger.info(
            "追記開始: %d bytes (位置 %d → %d)", new_size, last_position, file_size
        )
        blob_client.append_block(new_content)

        # ─ 位置を保存 ─
        with position_file.open("w") as f:
            json.dump(
                {
                    "last_position": file_size,
                    "last_mtime":    current_mtime,
                    "uploaded_at":   datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        logger.info("追記完了: %d bytes", new_size)
        return True

    except Exception as e:
        logger.error("アップロードエラー: %s: %s", type(e).__name__, e)
        import traceback
        logger.error(traceback.format_exc())
        return False

    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning("一時ファイル削除失敗: %s", e)


# ─────────────────────────────────────────────
#  エントリポイント
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
        logger.error("環境変数が未設定: AZURE_STORAGE_CONNECTION_STRING")
        sys.exit(1)

    logger.info("=== EcoFlow ログアップロード開始 ===")
    success = upload_log_file()
    logger.info("=== %s ===", "成功" if success else "失敗")
    sys.exit(0 if success else 1)
