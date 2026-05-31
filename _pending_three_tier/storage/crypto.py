"""Fernet encryption for FB token at rest.

Key source: FERNET_KEY env var (never hardcode).
Generate a key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _fernet():
    from cryptography.fernet import Fernet
    from config import FERNET_KEY

    if not FERNET_KEY:
        raise ValueError("FERNET_KEY env var not set — cannot encrypt/decrypt FB token")
    key = FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY
    return Fernet(key)


def encrypt_token(plaintext: str) -> str:
    """Fernet-encrypt plaintext token. Returns base64 ciphertext string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt ciphertext. Raises cryptography.fernet.InvalidToken if tampered."""
    return _fernet().decrypt(ciphertext.encode()).decode()
