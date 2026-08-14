"""Credential management — secure API key storage via OS keyring."""

import getpass
import keyring
import os
import json
import base64

SERVICE_NAME = "mecha"
KEY_NAME = "deepseek_api_key"
FALLBACK_DIR = os.path.expanduser("~/.mecha")
FALLBACK_FILE = os.path.join(FALLBACK_DIR, "credentials.enc")


def _keyring_available() -> bool:
    """Check if the OS keyring backend is available."""
    try:
        keyring.get_keyring()
        return True
    except Exception:
        return False


def set_key() -> str:
    """Prompt user to enter API key and store it securely.

    Returns:
        The keyring backend used ('keyring' or 'fallback').
    """
    key = getpass.getpass("Enter your DeepSeek API Key (input hidden): ")

    if _keyring_available():
        keyring.set_password(SERVICE_NAME, KEY_NAME, key)
        return "keyring"
    else:
        # Fallback: encrypted file with master password
        os.makedirs(FALLBACK_DIR, exist_ok=True)
        master = getpass.getpass("Set a master password for credential encryption: ")
        # Simple XOR-based obfuscation (not cryptographically secure, but better than plaintext)
        encoded = _xor_encode(key, master)
        with open(FALLBACK_FILE, "w", encoding="utf-8") as f:
            json.dump({"data": encoded}, f)
        return "fallback"


def get_key(master_password: str | None = None) -> str | None:
    """Retrieve the stored API key.

    Returns None if no key is stored.
    """
    if _keyring_available():
        return keyring.get_password(SERVICE_NAME, KEY_NAME)
    elif os.path.exists(FALLBACK_FILE):
        if master_password is None:
            master_password = getpass.getpass("Enter master password to unlock credentials: ")
        with open(FALLBACK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _xor_decode(data["data"], master_password)
    return None


def has_key() -> bool:
    """Check if a key is stored (without revealing it)."""
    if _keyring_available():
        return keyring.get_password(SERVICE_NAME, KEY_NAME) is not None
    return os.path.exists(FALLBACK_FILE)


def clear_key() -> None:
    """Remove the stored API key."""
    if _keyring_available():
        try:
            keyring.delete_password(SERVICE_NAME, KEY_NAME)
        except keyring.errors.PasswordDeleteError:
            pass
    if os.path.exists(FALLBACK_FILE):
        os.remove(FALLBACK_FILE)


def _xor_encode(text: str, key: str) -> str:
    """Simple XOR encoding for fallback storage."""
    key_bytes = key.encode("utf-8")
    text_bytes = text.encode("utf-8")
    result = bytes(text_bytes[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(text_bytes)))
    return base64.b64encode(result).decode("ascii")


def _xor_decode(encoded: str, key: str) -> str:
    """Decode XOR-encoded text."""
    key_bytes = key.encode("utf-8")
    data = base64.b64decode(encoded)
    result = bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))
    return result.decode("utf-8")