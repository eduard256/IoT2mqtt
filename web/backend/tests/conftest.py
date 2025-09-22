from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


_TEST_SECRETS_ROOT = Path(tempfile.mkdtemp(prefix="iot2mqtt-test-secrets-"))
_TEST_SECRETS_ROOT.mkdir(parents=True, exist_ok=True)
(_TEST_SECRETS_ROOT / ".master.key").write_bytes(Fernet.generate_key())

os.environ.setdefault("IOT2MQTT_SECRETS_PATH", str(_TEST_SECRETS_ROOT))


@pytest.fixture(autouse=True)
def reset_secrets_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IOT2MQTT_SECRETS_PATH", str(_TEST_SECRETS_ROOT))
