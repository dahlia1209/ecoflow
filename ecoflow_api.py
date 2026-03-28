"""
EcoFlow Open Platform HTTP API Client
https://developer-eu.ecoflow.com/us/document/introduction
"""

import hashlib
import hmac
import random
import time
import requests
from typing import Any
from dotenv import load_dotenv
import os

load_dotenv()


# ─────────────────────────────────────────────
#  設定
# ─────────────────────────────────────────────
BASE_URL   = "https://api-e.ecoflow.com"
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

# ─────────────────────────────────────────────
#  署名ユーティリティ
# ─────────────────────────────────────────────

def _flatten(obj: Any, prefix: str = "") -> dict[str, str]:
    """
    ネストされた dict / list を "key[0].sub=val" 形式にフラット化する。
    ドキュメント Step1・Step2 に対応。
    """
    items: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}.{k}" if prefix else k
            items.update(_flatten(v, new_key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{prefix}[{i}]"
            items.update(_flatten(v, new_key))
    else:
        items[prefix] = str(obj)
    return items


def _build_sign_str(params: dict, access_key: str, nonce: str, timestamp: str) -> str:
    """
    Step1-3: パラメータを ASCII 順にソートして署名文字列を生成する。
    """
    flat = _flatten(params)
    # ASCII 順ソート
    sorted_str = "&".join(f"{k}={v}" for k, v in sorted(flat.items()))
    # accessKey / nonce / timestamp を末尾に追加
    if sorted_str:
        sorted_str += f"&accessKey={access_key}&nonce={nonce}&timestamp={timestamp}"
    else:
        sorted_str = f"accessKey={access_key}&nonce={nonce}&timestamp={timestamp}"
    return sorted_str


def generate_sign(params: dict, access_key: str, secret_key: str) -> tuple[str, str, str]:
    """
    署名・nonce・timestamp を生成して返す。
    戻り値: (sign, nonce, timestamp)
    """
    nonce     = str(random.randint(100000, 999999))          # 6桁のランダム数
    timestamp = str(int(time.time() * 1000))                 # UTC ミリ秒

    sign_str  = _build_sign_str(params, access_key, nonce, timestamp)

    # Step4: HMAC-SHA256 で署名
    sign_bytes = hmac.new(
        secret_key.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    # Step5: バイト列を16進数文字列に変換
    sign = sign_bytes.hex()
    return sign, nonce, timestamp


def _build_headers(params: dict) -> dict[str, str]:
    """認証ヘッダーを生成する (Step6)"""
    sign, nonce, timestamp = generate_sign(params, ACCESS_KEY, SECRET_KEY)
    return {
        "accessKey": ACCESS_KEY,
        "nonce":     nonce,
        "timestamp": timestamp,
        "sign":      sign,
    }


# ─────────────────────────────────────────────
#  API メソッド
# ─────────────────────────────────────────────

def get_device_list() -> dict:
    """
    バインドされたデバイス一覧を取得する。
    GET /iot-open/sign/device/list
    """
    url     = f"{BASE_URL}/iot-open/sign/device/list"
    headers = _build_headers({})          # パラメータなし
    resp    = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_all_quota(sn: str) -> dict:
    """
    デバイスの全クォータ情報を取得する。
    GET /iot-open/sign/device/quota/all?sn=<sn>
    """
    url     = f"{BASE_URL}/iot-open/sign/device/quota/all"
    params  = {"sn": sn}
    headers = _build_headers(params)
    resp    = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_quota(sn: str, quota_keys: list[str], cmd_set: int, cmd_id: int) -> dict:
    """
    デバイスの指定クォータ情報を取得する。
    POST /iot-open/sign/device/quota
    """
    url  = f"{BASE_URL}/iot-open/sign/device/quota"
    body = {
        "sn": sn,
        "params": {
            "cmdSet": cmd_set,
            "id":     cmd_id,
            "quotas": quota_keys,
        },
    }
    headers = _build_headers(body)
    headers["Content-Type"] = "application/json;charset=UTF-8"
    resp = requests.post(url, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def set_device_quota(sn: str, params: dict) -> dict:
    """
    デバイスの機能を設定する。
    PUT /iot-open/sign/device/quota

    params 例 (Delta Pro X-Boost ON):
        {"cmdSet": 32, "id": 66, "enabled": 1}
    """
    url  = f"{BASE_URL}/iot-open/sign/device/quota"
    body = {"sn": sn, "params": params}
    headers = _build_headers(body)
    headers["Content-Type"] = "application/json;charset=UTF-8"
    resp = requests.put(url, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_mqtt_certification() -> dict:
    """
    MQTT 接続用の証明書情報を取得する。
    GET /iot-open/sign/certification
    """
    url     = f"{BASE_URL}/iot-open/sign/certification"
    headers = _build_headers({})
    resp    = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────
#  署名検証用テスト (ドキュメント記載の値で確認)
# ─────────────────────────────────────────────

def _verify_sign_example():
    """
    ドキュメントに記載されたテストベクタで署名生成を検証する。
    期待値: 07c13b65e037faf3b153d51613638fa80003c4c38d2407379a7f52851af1473e
    """
    test_access_key = "Fp4SvIprYSDPXtYJidEtUAd1o"
    test_secret_key = "WIbFEKre0s6sLnh4ei7SPUeYnptHG6V"
    test_nonce      = "345164"
    test_timestamp  = "1671171709428"
    test_params     = {
        "sn": "123456789",
        "params": {
            "cmdSet": 11,
            "id":     24,
            "eps":    0,
        },
    }
    sign_str = _build_sign_str(test_params, test_access_key, test_nonce, test_timestamp)
    sign_bytes = hmac.new(
        test_secret_key.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    sign = sign_bytes.hex()
    expected = "07c13b65e037faf3b153d51613638fa80003c4c38d2407379a7f52851af1473e"
    print(f"[署名検証]")
    print(f"  sign_str : {sign_str}")
    print(f"  生成値   : {sign}")
    print(f"  期待値   : {expected}")
    print(f"  結果     : {'✅ OK' if sign == expected else '❌ NG'}")


# ─────────────────────────────────────────────
#  使用例
# ─────────────────────────────────────────────

# if __name__ == "__main__":
#     import json

    # 1. 署名ロジックの検証
    # _verify_sign_example()
    # print()

    # 以下は ACCESS_KEY / SECRET_KEY を設定した上で実行してください

    # 2. デバイス一覧の取得
    # result = get_device_list()
    # print("デバイス一覧:", json.dumps(result, indent=2, ensure_ascii=False))

    # 3. 全クォータ取得 (sn はデバイスのシリアル番号)
    # SN = "DCABZ****"
    # result = get_all_quota(SN)
    # print("全クォータ:", json.dumps(result, indent=2, ensure_ascii=False))

    # 4. 特定クォータ取得 (Delta Pro の AC 有効フラグ)
    # result = get_quota(SN, ["inv.cfgAcEnabled"], cmd_set=32, cmd_id=66)
    # print("クォータ:", json.dumps(result, indent=2, ensure_ascii=False))

    # 5. デバイス設定変更 (Delta Pro X-Boost を ON)
    # result = set_device_quota(SN, {"cmdSet": 32, "id": 66, "enabled": 1})
    # print("設定結果:", json.dumps(result, indent=2, ensure_ascii=False))

    # 6. MQTT 証明書取得
    # result = get_mqtt_certification()
    # print("MQTT証明書:", json.dumps(result, indent=2, ensure_ascii=False))
