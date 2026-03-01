"""API key encryption/decryption using Fernet symmetric encryption."""
from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_FALLBACK_KEY_SEED = "inksight-local-dev-only"


def _get_fernet() -> Fernet:
    env_key = os.getenv("ENCRYPTION_KEY", "")
    if env_key:
        try:
            return Fernet(env_key)
        except Exception:
            derived = base64.urlsafe_b64encode(hashlib.sha256(env_key.encode()).digest())
            return Fernet(derived)
    derived = base64.urlsafe_b64encode(hashlib.sha256(_FALLBACK_KEY_SEED.encode()).digest())
    return Fernet(derived)


def encrypt_api_key(plaintext: str) -> str:
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception) as e:
        logger.warning(f"Failed to decrypt API key: {e}")
        return ""
