"""LLM key 单行加密存储，复用 core/crypto.py。"""
from __future__ import annotations

from typing import Any

from .db import get_conn, _lock


def get_llm_key() -> dict[str, Any]:
    """返回明文 key（已解密）。供渲染注入用。"""
    from core.crypto import decrypt_api_key

    with _lock:
        row = get_conn().execute("SELECT * FROM llm_key WHERE id=1").fetchone()
    if row is None:
        return {"provider": "deepseek", "api_key": "", "base_url": "", "image_api_key": ""}
    data = dict(row)
    out: dict[str, Any] = {
        "provider": data.get("provider") or "deepseek",
        "api_key": "",
        "base_url": data.get("base_url") or "",
        "image_api_key": "",
    }
    enc = data.get("api_key") or ""
    if enc:
        try:
            out["api_key"] = decrypt_api_key(enc)
        except Exception:
            out["api_key"] = ""
    enc_img = data.get("image_api_key") or ""
    if enc_img:
        try:
            out["image_api_key"] = decrypt_api_key(enc_img)
        except Exception:
            out["image_api_key"] = ""
    return out


def get_llm_key_masked() -> dict[str, Any]:
    """供管理页展示：key 脱敏。"""
    full = get_llm_key()
    return {
        "provider": full["provider"],
        "base_url": full["base_url"],
        "has_api_key": bool(full["api_key"]),
        "has_image_api_key": bool(full["image_api_key"]),
    }


def set_llm_key(patch: dict[str, Any]) -> dict[str, Any]:
    """部分更新。空字符串字段不覆盖（避免脱敏表单清空已存 key）。"""
    from core.crypto import encrypt_api_key

    cur = get_llm_key()
    provider = patch.get("provider", cur["provider"])
    base_url = patch.get("base_url", cur["base_url"])

    # api_key：只有显式传非空字符串才更新密文
    api_key_plain = cur["api_key"]
    if "api_key" in patch and patch["api_key"]:
        api_key_plain = str(patch["api_key"])
    image_api_key_plain = cur["image_api_key"]
    if "image_api_key" in patch and patch["image_api_key"]:
        image_api_key_plain = str(patch["image_api_key"])

    enc_api = encrypt_api_key(api_key_plain) if api_key_plain else ""
    enc_img = encrypt_api_key(image_api_key_plain) if image_api_key_plain else ""

    with _lock:
        conn = get_conn()
        conn.execute(
            "UPDATE llm_key SET provider=?, api_key=?, base_url=?, image_api_key=? WHERE id=1",
            (provider, enc_api, base_url, enc_img),
        )
        conn.commit()
    return get_llm_key_masked()