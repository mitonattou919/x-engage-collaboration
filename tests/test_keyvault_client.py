"""keyvault_client モジュールのユニットテスト"""
from unittest.mock import MagicMock, patch

import pytest

import keyvault_client
from keyvault_client import get_secret


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """各テスト前後に _get_client の lru_cache をクリア"""
    keyvault_client._get_client.cache_clear()
    yield
    keyvault_client._get_client.cache_clear()


def test_env_fallback_bypasses_keyvault(monkeypatch):
    monkeypatch.setenv("MY_SECRET", "env_value")
    result = get_secret("some-secret", env_fallback="MY_SECRET")
    assert result == "env_value"


def test_env_fallback_empty_falls_through_to_keyvault(monkeypatch):
    monkeypatch.delenv("MY_SECRET", raising=False)

    mock_client = MagicMock()
    mock_client.get_secret.return_value = MagicMock(value="kv_value")

    with patch("keyvault_client._get_client", return_value=mock_client):
        result = get_secret("some-secret", env_fallback="MY_SECRET")

    assert result == "kv_value"


def test_no_env_fallback_calls_keyvault(monkeypatch):
    mock_client = MagicMock()
    mock_client.get_secret.return_value = MagicMock(value="kv_value")

    with patch("keyvault_client._get_client", return_value=mock_client):
        result = get_secret("some-secret")

    assert result == "kv_value"
    mock_client.get_secret.assert_called_once_with("some-secret")


def test_keyvault_exception_reraises(monkeypatch):
    monkeypatch.delenv("MY_SECRET", raising=False)

    mock_client = MagicMock()
    mock_client.get_secret.side_effect = Exception("vault error")

    with patch("keyvault_client._get_client", return_value=mock_client):
        with pytest.raises(Exception, match="vault error"):
            get_secret("some-secret", env_fallback="MY_SECRET")
