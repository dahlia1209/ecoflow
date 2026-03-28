"""
EcoFlow RIVER 2 Pro — 定期データ取得ロガー
・取得間隔 : 1分
・保存形式  : JSON Lines (.jsonl)
・ログファイル: logs/ecoflow.jsonl （1ファイルに追記し続ける）
"""

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ecoflow_api import get_all_quota, get_device_list

# ─────────────────────────────────────────────
#  設定
# ─────────────────────────────────────────────
INTERVAL_SEC = 60                              # 取得間隔（秒）
LOG_DIR      = Path("logs")                    # ログ保存ディレクトリ
LOG_FILE     = LOG_DIR / "ecoflow.jsonl"       # ログファイル（固定）

# ─────────────────────────────────────────────
#  コンソールログ
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  graceful shutdown
# ─────────────────────────────────────────────
_running = True

def _handle_signal(signum, frame):
    global _running
    logger.info("シグナルを受信しました。ロガーを停止します...")
    _running = False

signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ─────────────────────────────────────────────
#  ログ書き込み
# ─────────────────────────────────────────────

def write_log(sn: str, data: dict) -> None:
    """1レコードを JSON Lines 形式でログファイルに追記する"""
    LOG_DIR.mkdir(exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sn":        sn,
        "data":      data,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("ログ書き込み完了 → %s  soc=%s%%  出力=%sW",
                LOG_FILE.name,
                data.get("pd.soc", "?"),
                data.get("pd.wattsOutSum", "?"))


# ─────────────────────────────────────────────
#  メインループ
# ─────────────────────────────────────────────

def main():
    logger.info("=== EcoFlow ロガー 起動 ===")

    # デバイス一覧からSNを取得
    try:
        device_resp = get_device_list()
        devices = device_resp.get("data", [])
        if not devices:
            logger.error("デバイスが見つかりません。ACCESS_KEY / SECRET_KEY を確認してください。")
            sys.exit(1)
    except Exception as e:
        logger.error("デバイス一覧の取得に失敗しました: %s", e)
        sys.exit(1)

    # 複数デバイスがある場合はすべてログ取得
    sns = [d["sn"] for d in devices]
    logger.info("対象デバイス: %s", sns)
    logger.info("取得間隔: %d 秒 / ログ保存先: %s", INTERVAL_SEC, LOG_FILE.resolve())

    while _running:
        for sn in sns:
            try:
                resp = get_all_quota(sn)
                if resp.get("code") == "0":
                    write_log(sn, resp["data"])
                else:
                    logger.warning("API エラー (sn=%s): %s", sn, resp.get("message"))
            except Exception as e:
                logger.error("取得失敗 (sn=%s): %s", sn, e)

        # INTERVAL_SEC 秒待機（1秒ごとに停止シグナルを確認）
        for _ in range(INTERVAL_SEC):
            if not _running:
                break
            time.sleep(1)

    logger.info("=== EcoFlow ロガー 停止 ===")


if __name__ == "__main__":
    main()
