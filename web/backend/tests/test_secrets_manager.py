from pathlib import Path

from services.secrets_manager import SecretsManager


def test_cipher_initialised_uses_env(tmp_path, monkeypatch):
    secrets_root = tmp_path / "custom-secrets"
    secrets_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("IOT2MQTT_SECRETS_PATH", str(secrets_root))

    manager = SecretsManager()

    assert manager.secrets_path == secrets_root
    assert manager.master_key_path.exists()
    assert manager.cipher is not None


def test_encrypt_decrypt_roundtrip():
    manager = SecretsManager()

    payload = {
        "token": "secret-value",
        "nested": {"password": "abc"}
    }

    encrypted = manager.encrypt_credentials(payload)
    decrypted = manager.decrypt_credentials(encrypted)

    assert decrypted == payload
