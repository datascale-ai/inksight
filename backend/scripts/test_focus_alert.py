import sys
from typing import Any, Dict

import requests


def main() -> None:
    if len(sys.argv) < 4:
        print("用法: python test_focus_alert.py <base_url> <mac> <alert_token>")
        print("示例: python test_focus_alert.py http://127.0.0.1:8000 AA:BB:CC:DD:EE:FF <设备alert_token>")
        print("")
        print("如何获取 alert_token：")
        print("1) 在 Web 配置页开启“专注监听”，弹窗会显示并可复制该设备的 alert_token（推荐）。")
        print("2) 或以 owner 身份调用：POST /api/device/{mac}/alert-token 获取。")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    mac = sys.argv[2]
    alert_token = sys.argv[3]

    url = f"{base_url}/api/device/{mac}/alert"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    headers["X-Agent-Token"] = alert_token

    payload: Dict[str, Any] = {
        "sender": "老板",
        "message": "服务器宕机，速看！",
        "level": "critical",
    }

    print(f"POST {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")

    resp = requests.post(url, json=payload, headers=headers, timeout=5)
    print(f"Status: {resp.status_code}")
    try:
        print("Body:", resp.json())
    except Exception:
        print("Body (raw):", resp.text)


if __name__ == "__main__":
    main()

