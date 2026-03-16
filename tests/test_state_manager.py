"""state_manager モジュールのユニットテスト"""
from unittest.mock import MagicMock, patch

import pytest
from azure.core.exceptions import ResourceNotFoundError

from state_manager import PARTITION_KEY, get_last_tweet_id, set_last_tweet_id


@patch("state_manager._get_client")
def test_get_last_tweet_id_returns_value(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_entity.return_value = {"last_tweet_id": "12345"}
    mock_get_client.return_value = mock_client

    result = get_last_tweet_id("testuser")

    assert result == "12345"
    mock_client.get_entity.assert_called_once_with(
        partition_key=PARTITION_KEY,
        row_key="testuser",
    )


@patch("state_manager._get_client")
def test_get_last_tweet_id_not_found_returns_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_entity.side_effect = ResourceNotFoundError("not found")
    mock_get_client.return_value = mock_client

    assert get_last_tweet_id("newuser") is None


@patch("state_manager._get_client")
def test_get_last_tweet_id_other_exception_returns_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_entity.side_effect = Exception("network error")
    mock_get_client.return_value = mock_client

    assert get_last_tweet_id("testuser") is None


@patch("state_manager._get_client")
def test_get_last_tweet_id_empty_value_returns_none(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_entity.return_value = {"last_tweet_id": ""}
    mock_get_client.return_value = mock_client

    assert get_last_tweet_id("testuser") is None


@patch("state_manager._get_client")
def test_get_last_tweet_id_lowercases_username(mock_get_client):
    mock_client = MagicMock()
    mock_client.get_entity.return_value = {"last_tweet_id": "99"}
    mock_get_client.return_value = mock_client

    get_last_tweet_id("TestUser")

    _, kwargs = mock_client.get_entity.call_args
    assert kwargs["row_key"] == "testuser"


@patch("state_manager._get_client")
def test_set_last_tweet_id_upserts_entity(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    set_last_tweet_id("testuser", "99999")

    mock_client.upsert_entity.assert_called_once_with(
        entity={
            "PartitionKey": PARTITION_KEY,
            "RowKey": "testuser",
            "last_tweet_id": "99999",
        }
    )


@patch("state_manager._get_client")
def test_set_last_tweet_id_lowercases_username(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    set_last_tweet_id("TestUser", "99999")

    _, kwargs = mock_client.upsert_entity.call_args
    assert kwargs["entity"]["RowKey"] == "testuser"


@patch("state_manager._get_client")
def test_set_last_tweet_id_raises_on_exception(mock_get_client):
    mock_client = MagicMock()
    mock_client.upsert_entity.side_effect = Exception("storage error")
    mock_get_client.return_value = mock_client

    with pytest.raises(Exception, match="storage error"):
        set_last_tweet_id("testuser", "99999")
